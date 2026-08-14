import logging
import os
import uuid
from contextvars import ContextVar
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Set by TenantMiddleware at the start of every request (and by the
# background jobs in main.py, once per tenant, outside any request). Read by
# the engine "begin" listener below — NOT by get_db() directly, because
# `SET LOCAL` only lasts for the current transaction, and most routes in this
# codebase commit mid-request and keep using the same session afterwards
# (e.g. `db.commit()` then `db.refresh(row)`). Each new transaction on this
# engine needs its own fresh `SET LOCAL`, so it's applied on every "begin",
# not once per request.
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:password_seguro@db:5432/elysium_agenda",
)

# Railway provides "postgresql://" — SQLAlchemy 2.x requires the +psycopg2 dialect explicitly
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# The running app connects at RUNTIME as APP_DATABASE_URL — a non-superuser
# role (see backend/scripts/bootstrap_app_role.sql) — so that Row-Level
# Security (alembic revision 0003) actually restricts anything. DATABASE_URL
# (the table owner, superuser in docker-compose today) always bypasses RLS
# regardless of FORCE ROW LEVEL SECURITY. Alembic never uses this value —
# it reads DATABASE_URL directly in alembic/env.py, since migrations need
# full DDL rights and must work before app_user/RLS exist at all.
_APP_DATABASE_URL = os.getenv("APP_DATABASE_URL")
_IS_PRODUCTION = os.getenv("RAILWAY_ENVIRONMENT") == "production"

if _APP_DATABASE_URL:
    if _APP_DATABASE_URL.startswith("postgresql://"):
        _APP_DATABASE_URL = _APP_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    _RUNTIME_DATABASE_URL = _APP_DATABASE_URL
elif _IS_PRODUCTION:
    # In production this can't be a warning — silently falling back to
    # DATABASE_URL means the app connects as the table owner/superuser,
    # which bypasses Row-Level Security entirely (RLS never restricts a
    # superuser or the table owner, regardless of FORCE ROW LEVEL SECURITY).
    # That's a full cross-tenant data leak, not a degraded feature, so
    # startup must abort rather than serve traffic in that state.
    raise RuntimeError(
        "APP_DATABASE_URL no configurada con RAILWAY_ENVIRONMENT=production. "
        "Sin ella el backend conectaría como superusuario/dueño de las tablas y "
        "Row-Level Security no protegería nada entre tenants. Configura "
        "APP_DATABASE_URL con el rol app_user (ver backend/scripts/bootstrap_app_role.sql) "
        "antes de arrancar en producción."
    )
else:
    logger.warning(
        "⚠️  APP_DATABASE_URL no configurada — el backend está conectando en runtime con "
        "DATABASE_URL (superusuario/owner). Row-Level Security no restringirá nada hasta que "
        "se configure APP_DATABASE_URL con el rol app_user (ver backend/scripts/bootstrap_app_role.sql)."
    )
    _RUNTIME_DATABASE_URL = DATABASE_URL

engine = create_engine(_RUNTIME_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "begin")
def _set_tenant_context(conn):
    """Fires at the start of every transaction on this engine. Postgres's
    SET does not accept bind parameters for its value — it must be a literal
    in the SQL text — so the contextvar is validated as a real UUID before
    being interpolated, which also rules out any injection risk (a valid
    uuid.UUID string only ever contains hex digits and dashes)."""
    raw = current_tenant_id.get()
    if raw is None:
        return  # no tenant context (e.g. resolving `tenants` itself) — RLS
        # then filters every row to zero, which is the safe default.
    validated = str(uuid.UUID(str(raw)))
    conn.exec_driver_sql(f"SET LOCAL app.tenant_id = '{validated}'")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
