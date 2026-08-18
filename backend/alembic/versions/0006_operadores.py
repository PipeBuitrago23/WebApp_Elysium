"""operadores — plataforma-level superadmin identity (sin tenant_id, sin RLS)

Fase 3 (panel superadmin). El dueño/operador de la plataforma, que da de alta y
administra tenants, necesita una identidad que vive FUERA del modelo por-tenant:
- no es una fila en `usuarios` (PK compuesta por tenant + FORCE RLS — un
  operador no pertenece a ningún tenant),
- vive al mismo nivel que `tenants`, que tampoco tiene `tenant_id` ni política
  RLS (se consulta para *resolver* un tenant antes de que exista contexto).

Por eso `operadores` se crea SIN columna `tenant_id` y **no** se agrega a la
lista de RLS de 0003: un superadmin tiene que ver/modificar todos los tenants,
lo opuesto al aislamiento por-tenant. Solo se alcanza por la conexión de
superadmin (`DATABASE_URL`, el rol dueño/superuser que bypassa RLS — la misma
que usan Alembic y crear_tenant.py), nunca por la conexión de runtime de un
tenant.

`REVOKE ALL ... FROM app_user`: defensa en profundidad. `app_user` es el rol
de runtime de cada request de tenant; nunca debe poder leer las credenciales
de superadmin, ni por un bug. El `ALTER DEFAULT PRIVILEGES` de
bootstrap_app_role.sql auto-otorgaría CRUD a `app_user` sobre cualquier tabla
nueva, así que acá se revoca explícito. Guardado con un `DO` por si el rol
`app_user` no existe todavía en ese entorno (una base fresca de CI sin el
bootstrap) — ahí el REVOKE simplemente se omite.

Escrita a mano (no autogenerate): toca una tabla sin `tenant_id` + DCL
(REVOKE), fuera del patrón tenant-scoped estándar.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operadores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("ultimo_login", sa.DateTime(), nullable=True),
    )
    op.create_unique_constraint("operadores_email_key", "operadores", ["email"])
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                REVOKE ALL ON operadores FROM app_user;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    op.drop_table("operadores")
