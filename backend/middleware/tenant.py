import logging
import os

from sqlalchemy import or_
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.constants import RESERVED_SLUGS
from database import SessionLocal, current_tenant_id
from models.tenant import Tenant

logger = logging.getLogger(__name__)


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
    3. DEFAULT_TENANT_SLUG env var — only if set and steps 1-2 didn't
       resolve anything. TEMPORARY bridge for the production cutover, which
       goes live before wildcard DNS for dimanik.com is connected: the
       backend's real Railway host (e.g. elysium-backend-production.up.
       railway.app) doesn't carry a tenant subdomain at all, so without this
       every request would 404 and the live client would have no service.
       Retire this env var once real subdomains resolve — see
       docs/CUTOVER.md's "retirar DEFAULT_TENANT_SLUG" step. Deliberately
       NOT gated by RAILWAY_ENVIRONMENT — production is exactly where it's
       needed, precisely because step 2 is disabled there.
    4. Otherwise: 404 with a neutral message — never reveals whether a slug
       exists or not. Also what happens if DEFAULT_TENANT_SLUG points at a
       slug that doesn't exist or is suspended — same generic 404, not an
       exception (the lookup below is a plain `.first()`, so a miss is just
       `None` flowing into the same check every other path already uses).

    A slug in RESERVED_SLUGS (core/constants.py) is never looked up against
    `tenants.slug` — those subdomains are reserved for infrastructure
    (admin/api/www/...), not real tenants, regardless of what a stray row
    might say. RESERVED_SLUGS deliberately does NOT apply to
    DEFAULT_TENANT_SLUG — that value is operator-set deployment config, not
    attacker-controlled input (unlike the Host header or X-Tenant-Slug), so
    there's nothing to guard against there. A tenant resolved with
    estado == "suspendido" is treated the same as not-found (404) — a
    suspended tenant used to still resolve correctly, which was a real gap.

    Sets request.state.tenant / request.state.tenant_id for the rest of the
    request, AND the `current_tenant_id` ContextVar (database.py) — the
    latter is what the SQLAlchemy engine's "begin" listener actually reads,
    since it has no access to the Request object.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health" or request.url.path.startswith("/superadmin"):
            # /health: deployment/orchestrator healthchecks hit this with no
            # tenant context at all (raw IP, internal hostname) — must never 404.
            # /superadmin/*: platform-level routes that operate ACROSS all
            # tenants (Fase 3) — they must not be tied to a single resolved
            # tenant. Their gate is require_superadmin + their own DB connection
            # (core/superadmin_db.py, DATABASE_URL), not the host. Path-based
            # exemption works in every environment (local, and Railway before
            # wildcard DNS), unlike keying on an `admin.` host.
            return await call_next(request)

        host = (request.headers.get("host") or "").split(":")[0]
        slug = _subdomain_from_host(host)
        if slug in RESERVED_SLUGS:
            slug = None

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
                if header_slug and header_slug not in RESERVED_SLUGS:
                    tenant = db.query(Tenant).filter(Tenant.slug == header_slug).first()

            if not tenant:
                default_slug = os.getenv("DEFAULT_TENANT_SLUG")
                if default_slug:
                    logger.warning(
                        "TenantMiddleware: Host=%r no resolvió a ningún tenant — usando "
                        "DEFAULT_TENANT_SLUG=%r como fallback temporal (puente pre-wildcard-DNS, "
                        "ver docs/CUTOVER.md).",
                        host, default_slug,
                    )
                    tenant = db.query(Tenant).filter(Tenant.slug == default_slug).first()
        finally:
            db.close()

        if not tenant or tenant.estado == "suspendido":
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
