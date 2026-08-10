import os

from sqlalchemy import or_
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from database import SessionLocal, current_tenant_id
from models.tenant import Tenant


def _subdomain_from_host(host: str) -> str | None:
    """Leftmost label of the Host header as a candidate tenant slug. Returns
    None for hosts with no meaningful subdomain (localhost, bare IPs, or a
    bare base domain like "tuestudio.app") — those rely on X-Tenant-Slug
    instead (see TenantMiddleware.dispatch, non-production only)."""
    if not host or host == "localhost" or host.replace(".", "").isdigit():
        return None
    parts = host.split(".")
    if len(parts) < 3:
        return None
    return parts[0]


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolves the tenant for every request, in this strict order:
    1. Subdomain of the Host header (or an exact match against a tenant's
       custom_domain — the column exists on the model already; this doesn't
       need wildcard DNS to be wired, it just won't be reachable without it).
    2. X-Tenant-Slug header — only when RAILWAY_ENVIRONMENT != "production"
       (local/dev convenience, since localhost has no real subdomain).
    3. Otherwise: 404 with a neutral message — never reveals whether a slug
       exists or not.

    Sets request.state.tenant / request.state.tenant_id for the rest of the
    request, AND the `current_tenant_id` ContextVar (database.py) — the
    latter is what the SQLAlchemy engine's "begin" listener actually reads,
    since it has no access to the Request object.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            # Deployment/orchestrator healthchecks hit this with no tenant
            # context at all (raw IP, internal hostname) — must never 404.
            return await call_next(request)

        host = (request.headers.get("host") or "").split(":")[0]
        slug = _subdomain_from_host(host)

        db = SessionLocal()
        try:
            tenant = None
            conditions = []
            if slug:
                conditions.append(Tenant.slug == slug)
            if host:
                conditions.append(Tenant.custom_domain == host)
            if conditions:
                tenant = db.query(Tenant).filter(or_(*conditions)).first()

            if not tenant and os.getenv("RAILWAY_ENVIRONMENT") != "production":
                header_slug = request.headers.get("x-tenant-slug")
                if header_slug:
                    tenant = db.query(Tenant).filter(Tenant.slug == header_slug).first()
        finally:
            db.close()

        if not tenant:
            return JSONResponse(status_code=404, content={"detail": "No encontrado"})

        request.state.tenant = tenant
        request.state.tenant_id = str(tenant.id)

        token = current_tenant_id.set(str(tenant.id))
        try:
            return await call_next(request)
        finally:
            current_tenant_id.reset(token)


def get_current_tenant(request: Request) -> Tenant:
    """FastAPI dependency — `tenant: Tenant = Depends(get_current_tenant)` —
    for routes that need tenant.get_config(...) (schedule window, plan
    expiry, etc). Just reads what TenantMiddleware already resolved."""
    return request.state.tenant
