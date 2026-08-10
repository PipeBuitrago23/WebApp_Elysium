"""row-level security — tenant_isolation policy on every tenant-scoped table

Kept as its own revision, separate from 0002: if something is wrong with the
RLS policy it can be rolled back on its own without re-running the (much
riskier) key-reconstruction migration. `admin` (the table owner, superuser in
docker-compose today) still bypasses RLS regardless of FORCE ROW LEVEL
SECURITY — a superuser always bypasses RLS. For the policy to have any real
effect, the running app must connect as a genuinely different, non-superuser
role (`app_user`, bootstrapped separately — see
backend/scripts/bootstrap_app_role.sql, kept out of Alembic on purpose: it's
cluster-wide DCL and needs a per-environment secret).

`servicios` is included (it has tenant_id and is exactly the kind of
per-tenant data — capacities, durations, catalog — that must not leak).
`tenants` is excluded: it's queried to *resolve* a tenant before any
`app.tenant_id` context exists, and it has no tenant_id column of its own.

`current_setting('app.tenant_id', true)` returns NULL when the GUC has
*never* been touched on this connection (the `true` = missing_ok arg avoids
an error). But `SET LOCAL` reverts to the GUC's prior value when its
transaction ends — and on a **pooled connection that previously had
`app.tenant_id` set** (by an earlier, committed request), that prior value is
an empty string `''`, not NULL. Verified empirically: same session,
`SET LOCAL app.tenant_id = '<uuid>'; COMMIT;` then a later transaction with no
`SET LOCAL` sees `current_setting(...) = ''`. Casting `''::uuid` directly
raises `invalid input syntax for type uuid`, not a clean "0 rows" — so the
policy wraps it in `NULLIF(..., '')` to fold that empty-string case back to a
real NULL before casting. This is required for correctness on a pooled
connection (i.e. always, in this app) — relying on the application to always
proactively clear `app.tenant_id` on every code path would be far more
fragile than fixing it once here. With that in place, no context (fresh
connection or post-request pooled reuse) safely means zero rows for USING and
a rejected write for WITH CHECK (covers acceptance criterion #3).

Foreign key checks always bypass RLS (documented Postgres behavior) — RLS on
tenant_id alone would not stop a bug where citas.tenant_id is correct but
citas.paciente_id points at a different tenant's patient. That gap is closed
by the composite FKs added in 0002, not by RLS; the two are complementary.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_ISOLATED_TABLES = (
    "pacientes", "usuarios", "citas", "pagos", "ventas", "gastos", "servicios",
)


def upgrade() -> None:
    for table in TENANT_ISOLATED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )


def downgrade() -> None:
    for table in TENANT_ISOLATED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
