"""Superadmin panel (Fase 3) — aislación de auth y paridad CLI/endpoint.

Cubre lo que NO alcanza con revisar a ojo:
- un JWT de superadmin NUNCA es aceptado por una ruta de tenant, y
- un JWT normal de tenant (aunque sea es_admin) NUNCA es aceptado por una
  ruta de superadmin — en ambos sentidos.
- rate limit del login de superadmin.
- suspender/eliminar un operador invalida sus tokens ya emitidos.
- crear_tenant.py (vía core.tenants.crear_tenant, su mismo code path) y el
  endpoint POST /superadmin/tenants producen la misma estructura.

Corre dentro del contenedor backend (mismo entorno que test_tenant_isolation):

    docker compose exec backend pytest

Cada test crea sus propios operadores/tenants desechables y los limpia; nunca
toca los datos reales de Elysium.
"""
import os
import uuid

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from auth.jwt import create_access_token
from auth.superadmin import create_superadmin_token
from core.tenants import crear_tenant as core_crear_tenant
from limiter import limiter
from main import app
from models.operador import Operador

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:password_seguro@db:5432/elysium_agenda"
).replace("postgresql://", "postgresql+psycopg2://", 1)

# admin_engine: rol dueño/superuser (bypassa RLS) — el mismo que usan Alembic,
# crear_tenant.py y la conexión de superadmin. Se usa acá para setup/teardown.
admin_engine = create_engine(DATABASE_URL)
AdminSession = sessionmaker(bind=admin_engine)


def _make_operador(conn, email: str, password: str, activo: bool = True) -> str:
    op_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        text(
            """
            INSERT INTO operadores (id, email, hashed_password, nombre, activo)
            VALUES (:id, :email, :h, 'Operador Test', :activo)
            """
        ),
        {"id": op_id, "email": email, "h": hashed, "activo": activo},
    )
    return op_id


def _delete_operador(conn, email: str) -> None:
    conn.execute(text("DELETE FROM operadores WHERE email = :email"), {"email": email})


def _make_tenant(conn, slug: str, plan: str = "completo") -> str:
    tid = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO tenants (id, slug, nombre_comercial, plan, estado, config)
            VALUES (:id, :slug, :slug, :plan, 'activo', '{}'::jsonb)
            """
        ),
        {"id": tid, "slug": slug, "plan": plan},
    )
    return tid


def _delete_tenant(conn, tid: str) -> None:
    for table in ("citas", "pagos", "ventas", "gastos", "pacientes", "usuarios", "servicios"):
        conn.execute(text(f"DELETE FROM {table} WHERE tenant_id = :tid"), {"tid": tid})
    conn.execute(text("DELETE FROM tenants WHERE id = :tid"), {"tid": tid})


def _token_for(op_id: str, email: str) -> str:
    """Mint a superadmin token directly (no login endpoint) — así los tests de
    aislación no consumen el presupuesto de rate limit del login."""
    return create_superadmin_token(Operador(id=op_id, email=email))


@pytest.fixture
def client():
    # Sin `with`: lifespan no corre (no seeds, no jobs). TenantMiddleware y las
    # rutas están montadas en import time, así que se ejercita lo real igual.
    return TestClient(app)


@pytest.fixture
def operador():
    email = f"op-{uuid.uuid4().hex[:8]}@test.local"
    password = "operador-pass-123"
    with admin_engine.begin() as conn:
        op_id = _make_operador(conn, email, password)
    yield {"id": op_id, "email": email, "password": password}
    with admin_engine.begin() as conn:
        _delete_operador(conn, email)


@pytest.fixture
def tenant():
    slug = f"test-sa-{uuid.uuid4().hex[:8]}"
    with admin_engine.begin() as conn:
        tid = _make_tenant(conn, slug)
    yield {"id": tid, "slug": slug}
    with admin_engine.begin() as conn:
        _delete_tenant(conn, tid)


# ── Login: happy path + rate limit ───────────────────────────────────────────

def test_superadmin_login_ok(client, operador):
    # Limiter apagado para que el happy-path sea determinista, sin depender del
    # presupuesto que otros tests puedan haber consumido.
    original = limiter.enabled
    limiter.enabled = False
    try:
        resp = client.post(
            "/superadmin/auth/login",
            data={"username": operador["email"], "password": operador["password"]},
        )
        assert resp.status_code == 200
        assert resp.json()["token_type"] == "bearer"
        assert resp.json()["access_token"]
    finally:
        limiter.enabled = original


def test_superadmin_login_rate_limited(client, operador):
    original = limiter.enabled
    limiter.enabled = True
    try:
        # 8 intentos seguidos (>5/min) garantizan cruzar el límite aunque algún
        # otro test haya consumido parte de la ventana. Password incorrecta a
        # propósito: el rate limit corre antes de validar credenciales.
        codes = [
            client.post(
                "/superadmin/auth/login",
                data={"username": operador["email"], "password": "mala"},
            ).status_code
            for _ in range(8)
        ]
        assert 429 in codes
    finally:
        limiter.enabled = original


# ── Aislación cruzada tenant ↔ superadmin (ambos sentidos) ───────────────────

def test_superadmin_token_rejected_by_tenant_route(client, operador, tenant):
    token = _token_for(operador["id"], operador["email"])
    resp = client.get(
        "/pacientes/",
        headers={"X-Tenant-Slug": tenant["slug"], "Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_tenant_admin_token_rejected_by_superadmin_route(client):
    # Token de admin de un tenant (firmado con JWT_SECRET_KEY, no con el de
    # superadmin) — no debe pasar require_superadmin.
    token = create_access_token({
        "sub": "admin@algun-tenant.com",
        "tenant_id": str(uuid.uuid4()),
        "es_admin": True,
        "es_medico": False,
    })
    resp = client.get("/superadmin/tenants/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_no_token_rejected_by_superadmin_route(client):
    assert client.get("/superadmin/tenants/").status_code == 401


def test_suspended_operador_token_rejected(client, operador):
    token = _token_for(operador["id"], operador["email"])
    # El token es válido, pero suspender al operador debe cortarlo de inmediato.
    with admin_engine.begin() as conn:
        conn.execute(
            text("UPDATE operadores SET activo = false WHERE id = :id"),
            {"id": operador["id"]},
        )
    resp = client.get("/superadmin/tenants/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ── Paridad CLI ↔ endpoint ───────────────────────────────────────────────────

def _estructura(conn, tid: str) -> dict:
    servicios = conn.execute(
        text("SELECT nombre, capacidad, duracion_min, activo FROM servicios WHERE tenant_id = :tid ORDER BY nombre"),
        {"tid": tid},
    ).fetchall()
    admins = conn.execute(
        text("SELECT email FROM usuarios WHERE tenant_id = :tid AND es_admin = true"),
        {"tid": tid},
    ).fetchall()
    plan, estado = conn.execute(
        text("SELECT plan, estado FROM tenants WHERE id = :tid"), {"tid": tid}
    ).fetchone()
    return {
        "servicios": [tuple(r) for r in servicios],
        "num_admins": len(admins),
        "plan": plan,
        "estado": estado,
    }


def test_cli_and_endpoint_produce_same_tenant(client, operador):
    slug_ep = f"test-ep-{uuid.uuid4().hex[:8]}"
    slug_cli = f"test-cli-{uuid.uuid4().hex[:8]}"
    token = _token_for(operador["id"], operador["email"])

    # (a) vía endpoint
    resp = client.post(
        "/superadmin/tenants/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "slug": slug_ep, "nombre": "EP", "plan": "completo",
            "admin_email": "admin@ep.com", "admin_nombre": "Admin EP",
        },
    )
    assert resp.status_code == 201

    # (b) vía el MISMO code path del CLI (core.tenants.crear_tenant)
    db = AdminSession()
    try:
        core_crear_tenant(
            db, slug=slug_cli, nombre="CLI", plan="completo",
            admin_email="admin@cli.com", admin_nombre="Admin CLI",
        )
        db.commit()
    finally:
        db.close()

    try:
        with admin_engine.begin() as conn:
            tid_ep = conn.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": slug_ep}).scalar()
            tid_cli = conn.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": slug_cli}).scalar()
            est_ep = _estructura(conn, tid_ep)
            est_cli = _estructura(conn, tid_cli)

        # Misma estructura: 2 servicios idénticos (nombre/capacidad/duración),
        # exactamente un admin, mismo plan/estado.
        assert est_ep["servicios"] == est_cli["servicios"]
        assert est_ep["num_admins"] == est_cli["num_admins"] == 1
        assert est_ep["plan"] == est_cli["plan"] == "completo"
        assert est_ep["estado"] == est_cli["estado"] == "activo"
    finally:
        with admin_engine.begin() as conn:
            for s in (slug_ep, slug_cli):
                tid = conn.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": s}).scalar()
                if tid:
                    _delete_tenant(conn, tid)
