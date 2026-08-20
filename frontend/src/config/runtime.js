// Derives which tenant/backend this page is serving from window.location at
// runtime, instead of anything baked into the build.
//
// Wildcard-DNS mode (the end goal): when a real REACT_APP_BASE_DOMAIN is
// configured, the browser host is <slug>.<BASE_DOMAIN> and the backend lives at
// <slug>.api.<BASE_DOMAIN> — so one build serves every tenant, deriving both
// from window.location. That mode only kicks in when BASE_DOMAIN is a real
// domain AND we're not on localhost.
//
// Until wildcard DNS is actually connected, production runs on FIXED Railway
// domains (frontend at marvelous-…up.railway.app, backend at
// webappelysium-production…up.railway.app) that don't follow the <slug>.<base>
// scheme. In that window we must fall back to the explicit REACT_APP_API_URL
// (baked at build time) instead of deriving a bogus <slug>.api.undefined URL.
// The tenant is resolved server-side via DEFAULT_TENANT_SLUG there, and
// X-Tenant-Slug is ignored by the backend in production anyway — so the exact
// tenantSlug value doesn't matter in this fallback. Same fallback covers
// localhost dev. Remove this fallback once wildcard DNS is live (it becomes a
// no-op once BASE_DOMAIN is set and hosts follow the scheme).
const hostname = window.location.hostname;
const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
const baseDomain = process.env.REACT_APP_BASE_DOMAIN;

const useWildcard = !isLocal && !!baseDomain && baseDomain !== 'localhost';

export const tenantSlug = useWildcard
  ? hostname.split('.')[0]
  : process.env.REACT_APP_DEV_TENANT_SLUG;

export const apiUrl = useWildcard
  ? `https://${tenantSlug}.api.${baseDomain}`
  : (process.env.REACT_APP_API_URL || 'http://localhost:8000');
