from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text
from database import Base


class Operador(Base):
    """Plataforma-level superadmin — the platform owner/operator who provisions
    and manages tenants (Fase 3). Deliberately NOT a row in `usuarios`: that
    table is partitioned per tenant (composite PK `(tenant_id, id)`, FORCE RLS),
    and an operador belongs to no tenant. Lives at the same level as `tenants`
    itself — no `tenant_id`, and 0006 never adds it to 0003's RLS list, because
    a superadmin must see/modify every tenant (the opposite of per-tenant
    isolation).

    Reached only through the superadmin DB connection (`DATABASE_URL`, the
    RLS-bypassing owner/superuser — same connection Alembic and crear_tenant.py
    use). The runtime tenant role `app_user` is explicitly `REVOKE`d from this
    table in 0006, so a tenant request can never read superadmin credentials.
    """
    __tablename__ = "operadores"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nombre = Column(String, nullable=False)
    activo = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
    ultimo_login = Column(DateTime, nullable=True)
