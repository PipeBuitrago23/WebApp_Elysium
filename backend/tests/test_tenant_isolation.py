"""Multi-tenant Phase 1 isolation tests — covers acceptance criteria 1-7 from
the multi-tenant plan (RLS isolation, cross-tenant JWT rejection, feature
flags, cross-tenant uniqueness). Criteria 8-9 (production dump migration,
alembic downgrade) are verified manually, not here — see CLAUDE.md.

Also covers the DEFAULT_TENANT_SLUG fallback added for the production
cutover (temporary bridge until wildcard DNS for dimanik.com is connected —
see docs/CUTOVER.md and middleware/tenant.py's docstring).

Requires a real Postgres with RLS applied (alembic head) and the app_user
role bootstrapped (backend/scripts/bootstrap_app_role.sql) — RLS cannot be
tested against SQLite. Run inside the backend container, where DATABASE_URL
and APP_DATABASE_URL already point at the docker-compose Postgres:

    docker compose exec backend pytest

Every test creates its own throwaway tenant(s) (via the `tenant`/`two_tenants`
fixtures) and cleans them up afterward — never touches the real Elysium data.
"""
import os
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from main import app

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:password_seguro@db:5432/elysium_agenda"
).replace("postgresql://", "postgresql+psycopg2://", 1)
APP_DATABASE_URL = os.getenv(
    "APP_DATABASE_URL", "postgresql://app_user:app_user_dev_pw@db:5432/elysium_agenda"
).replace("postgresql://", "postgresql+psycopg2://", 1)

# admin_engine: table owner / superuser — bypasses RLS, used only for
# test setup/teardown (seeding tenants, cleaning up), never to assert isolation.
admin_engine = create_engine(DATABASE_URL)
# app_engine: same role the running app actually connects as — RLS applies.
app_engine = create_engine(APP_DATABASE_URL)


def _set_tenant(conn, tenant_id: str) -> None:
    """SET LOCAL doesn't accept bind parameters in Postgres — the value must
    be a literal in the SQL text. Safe here because tenant_id is always a
    uuid4 string this test generated itself, never external input (same
    reasoning as database.py's real "begin" listener)."""
    conn.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


def _make_tenant(conn, slug: str, plan: str = "completo") -> str:
    tenant_id = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO tenants (id, slug, nombre_comercial, plan, estado, config)
            VALUES (:id, :slug, :slug, :plan, 'activo', '{}'::jsonb)
            """
        ),
        {"id": tenant_id, "slug": slug, "plan": plan},
    )
    conn.execute(
        text(
            """
            INSERT INTO servicios (tenant_id, nombre, capacidad, duracion_min, activo)
            VALUES (:tid, 'Pilates', 6, 60, true)
            """
        ),
        {"tid": tenant_id},
    )
    return tenant_id


def _delete_tenant(conn, tenant_id: str) -> None:
    for table in ("citas", "pagos", "ventas", "gastos", "pacientes", "usuarios", "servicios"):
        conn.execute(text(f"DELETE FROM {table} WHERE tenant_id = :tid"), {"tid": tenant_id})
    conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": tenant_id})


@pytest.fixture
def two_tenants():
    """Fresh pair of throwaway tenants per test — function-scoped so tests
    that mutate tenant state (plan, features_override) never leak into
    each other."""
    with admin_engine.begin() as conn:
        tid_a = _make_tenant(conn, f"test-a-{uuid.uuid4().hex[:8]}")
        tid_b = _make_tenant(conn, f"test-b-{uuid.uuid4().hex[:8]}")
    yield {"a": tid_a, "b": tid_b}
    with admin_engine.begin() as conn:
        _delete_tenant(conn, tid_a)
        _delete_tenant(conn, tid_b)


@pytest.fixture
def client():
    # Plain TestClient (no `with`) — lifespan never runs, so this skips the
    # Elysium-specific _seed_admin()/_seed_paciente() and the background
    # jobs. TenantMiddleware and the RLS "begin" listener are both wired at
    # import time in main.py/database.py, independent of lifespan, so the
    # tests below exercise the real thing either way.
    return TestClient(app)


# ── 1-3: RLS isolation at the SQL level (app_user, same role the app uses) ──

def test_select_without_where_is_isolated_to_current_tenant(two_tenants):
    tid_a, tid_b = two_tenants["a"], two_tenants["b"]
    with admin_engine.begin() as conn:
        conn.execute(
            text('INSERT INTO pacientes (tenant_id, "Paciente", nombre) VALUES (:tid, :ced, :n)'),
            {"tid": tid_a, "ced": "900000001", "n": "Paciente A"},
        )
        conn.execute(
            text('INSERT INTO pacientes (tenant_id, "Paciente", nombre) VALUES (:tid, :ced, :n)'),
            {"tid": tid_b, "ced": "900000002", "n": "Paciente B"},
        )

    with app_engine.connect() as conn:
        with conn.begin():
            _set_tenant(conn, tid_a)
            rows = conn.execute(text('SELECT "Paciente" FROM pacientes')).fetchall()

    assert {r[0] for r in rows} == {"900000001"}


def test_insert_with_mismatched_tenant_id_is_rejected(two_tenants):
    tid_a, tid_b = two_tenants["a"], two_tenants["b"]
    with pytest.raises(Exception):
        with app_engine.connect() as conn:
            with conn.begin():
                _set_tenant(conn, tid_a)
                conn.execute(
                    text('INSERT INTO pacientes (tenant_id, "Paciente", nombre) VALUES (:tid, :ced, :n)'),
                    {"tid": tid_b, "ced": "900000099", "n": "Intruso"},
                )


def test_no_tenant_context_returns_zero_rows(two_tenants):
    with admin_engine.begin() as conn:
        conn.execute(
            text('INSERT INTO pacientes (tenant_id, "Paciente", nombre) VALUES (:tid, :ced, :n)'),
            {"tid": two_tenants["a"], "ced": "900000003", "n": "X"},
        )

    with app_engine.connect() as conn:
        with conn.begin():
            rows = conn.execute(text("SELECT * FROM pacientes")).fetchall()

    assert rows == []


# ── 4: cross-tenant JWT rejection (API level) ────────────────────────────

def test_jwt_from_one_tenant_rejected_against_another(client, two_tenants):
    with admin_engine.begin() as conn:
        slug_a = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["a"]}).scalar()
        slug_b = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["b"]}).scalar()
        hashed = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode()
        conn.execute(
            text(
                """
                INSERT INTO usuarios (id, tenant_id, email, hashed_password, nombre, es_admin, habeas_data_aceptado)
                VALUES (:id, :tid, 'admin@test-a.com', :hp, 'Test Admin A', true, true)
                """
            ),
            {"id": str(uuid.uuid4()), "tid": two_tenants["a"], "hp": hashed},
        )

    login = client.post(
        "/auth/login",
        headers={"X-Tenant-Slug": slug_a},
        data={"username": "admin@test-a.com", "password": "testpass123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    same_tenant = client.get("/citas/", headers={"X-Tenant-Slug": slug_a, "Authorization": f"Bearer {token}"})
    assert same_tenant.status_code == 200

    cross_tenant = client.get("/citas/", headers={"X-Tenant-Slug": slug_b, "Authorization": f"Bearer {token}"})
    assert cross_tenant.status_code == 401


# ── 5-6: feature flags ────────────────────────────────────────────────────

def test_basico_plan_gets_403_on_ventas(client, two_tenants):
    with admin_engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET plan = 'basico' WHERE id = :tid"), {"tid": two_tenants["b"]})
        slug_b = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["b"]}).scalar()

    resp = client.get("/ventas/", headers={"X-Tenant-Slug": slug_b})
    assert resp.status_code == 403


def test_features_override_grants_access_past_plan_default(client, two_tenants):
    with admin_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE tenants
                SET plan = 'basico', features_override = '{"habilitadas": ["ventas"]}'::jsonb
                WHERE id = :tid
                """
            ),
            {"tid": two_tenants["b"]},
        )
        slug_b = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["b"]}).scalar()

    resp = client.get("/ventas/", headers={"X-Tenant-Slug": slug_b})
    # The feature gate no longer blocks (no more 403) — what's left is the
    # auth check (401, no token sent), which is a separate concern from
    # this criterion.
    assert resp.status_code != 403


# ── 7: cross-tenant uniqueness (same cedula / email, different tenants) ──

def test_same_cedula_and_email_across_two_tenants_do_not_collide(two_tenants):
    tid_a, tid_b = two_tenants["a"], two_tenants["b"]

    for tid, nombre in ((tid_a, "Paciente A"), (tid_b, "Paciente B")):
        with app_engine.connect() as conn:
            with conn.begin():
                _set_tenant(conn, tid)
                conn.execute(
                    text('INSERT INTO pacientes (tenant_id, "Paciente", nombre) VALUES (:tid, :ced, :n)'),
                    {"tid": tid, "ced": "900000777", "n": nombre},
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO usuarios (id, tenant_id, email, hashed_password, nombre)
                        VALUES (:id, :tid, 'dup@test.com', 'x', :n)
                        """
                    ),
                    {"id": str(uuid.uuid4()), "tid": tid, "n": nombre},
                )

    with admin_engine.connect() as conn:
        count = conn.execute(
            text('SELECT count(*) FROM pacientes WHERE "Paciente" = :ced'), {"ced": "900000777"}
        ).scalar()
    assert count == 2


# ── DEFAULT_TENANT_SLUG fallback — temporary cutover bridge, see docs/CUTOVER.md ──
# "xxx-production.up.railway.app" stands in for the backend's real Railway
# host: 3+ labels, so _subdomain_from_host treats "xxx-production" as a
# slug candidate, but no tenant is ever named that — the lookup always
# misses, exactly like the real pre-wildcard-DNS cutover scenario this
# fallback exists for.
_UNRESOLVABLE_HOST = "xxx-production.up.railway.app"


def test_default_tenant_slug_resolves_when_host_does_not(client, monkeypatch):
    with admin_engine.begin() as conn:
        tid = _make_tenant(conn, f"test-default-{uuid.uuid4().hex[:8]}")
        slug = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": tid}).scalar()
    try:
        monkeypatch.setenv("DEFAULT_TENANT_SLUG", slug)
        resp = client.get("/tenant/config", headers={"Host": _UNRESOLVABLE_HOST})
        assert resp.status_code == 200
        assert resp.json()["nombre_comercial"] == slug
    finally:
        with admin_engine.begin() as conn:
            _delete_tenant(conn, tid)


def test_no_default_tenant_slug_returns_404_when_host_does_not_resolve(client, monkeypatch):
    monkeypatch.delenv("DEFAULT_TENANT_SLUG", raising=False)
    resp = client.get("/tenant/config", headers={"Host": _UNRESOLVABLE_HOST})
    assert resp.status_code == 404


def test_valid_host_subdomain_takes_precedence_over_default_tenant_slug(client, monkeypatch, two_tenants):
    with admin_engine.begin() as conn:
        slug_a = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["a"]}).scalar()
        slug_b = conn.execute(text("SELECT slug FROM tenants WHERE id = :tid"), {"tid": two_tenants["b"]}).scalar()

    # DEFAULT_TENANT_SLUG points at tenant B, but the Host resolves to
    # tenant A via a real subdomain — A must win.
    monkeypatch.setenv("DEFAULT_TENANT_SLUG", slug_b)
    resp = client.get("/tenant/config", headers={"Host": f"{slug_a}.api.test.com"})
    assert resp.status_code == 200
    assert resp.json()["nombre_comercial"] == slug_a
