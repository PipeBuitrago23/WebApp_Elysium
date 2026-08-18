import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Superadmin routes must see and modify EVERY tenant at once — incompatible with
# database.py's runtime engine (APP_DATABASE_URL / app_user, subject to RLS with
# a single SET LOCAL app.tenant_id per transaction). So, exactly like
# crear_tenant.py, this uses its own engine bound to DATABASE_URL — the
# owner/superuser role that bypasses RLS. Deliberately NOT database.py's engine:
# that one is wired to APP_DATABASE_URL AND to the tenant-context "begin"
# listener, neither of which applies here (this engine has no such listener, so
# its transactions never try to SET LOCAL a tenant — precisely the point).
#
# REQUIREMENT: DATABASE_URL must be a role that bypasses RLS (superuser or a
# BYPASSRLS role — the same role Alembic and crear_tenant.py already require).
# If it points at app_user (subject to FORCE ROW LEVEL SECURITY), cross-tenant
# reads of tenant-scoped tables return nothing and creating a tenant fails on
# the servicios/usuarios INSERTs (RLS WITH CHECK). `operadores` and `tenants`
# have no RLS, so listing/creating/updating tenants works regardless — but
# reading a tenant's servicios in the detail view needs the RLS bypass.
_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:password_seguro@db:5432/elysium_agenda"
)
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

superadmin_engine = create_engine(_DATABASE_URL)
SuperadminSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=superadmin_engine)


def get_superadmin_db():
    db = SuperadminSessionLocal()
    try:
        yield db
    finally:
        db.close()
