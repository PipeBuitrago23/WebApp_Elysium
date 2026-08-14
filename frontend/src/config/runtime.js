// Derives which tenant/backend this page is serving from window.location at
// runtime, instead of anything baked into the build. One frontend build has
// to work for every tenant — <slug>.<BASE_DOMAIN> in the browser tells us
// both who the tenant is and where its backend lives
// (<slug>.api.<BASE_DOMAIN>), so nothing tenant-specific belongs in an env
// var read at build time except the local-dev fallback below.
const hostname = window.location.hostname;
const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';

// localhost has no real subdomain — REACT_APP_DEV_TENANT_SLUG (sent as the
// X-Tenant-Slug header, honored by the backend only when
// RAILWAY_ENVIRONMENT != "production") stands in for it.
export const tenantSlug = isLocal
  ? process.env.REACT_APP_DEV_TENANT_SLUG
  : hostname.split('.')[0];

export const apiUrl = isLocal
  ? (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  : `https://${tenantSlug}.api.${process.env.REACT_APP_BASE_DOMAIN}`;
