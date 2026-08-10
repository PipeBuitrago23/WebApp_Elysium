import axios from 'axios';

// Single axios instance for the whole app — replaces the API_URL +
// authHeaders() pattern that used to be hand-copied in every api/*.js file.
// The tenant-resolution plumbing needs one place to inject headers on every
// request; keeping the old duplication would mean repeating it 9 times.
export const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Dev-only convenience: localhost has no real subdomain, so the backend
// falls back to this header to resolve the tenant (TenantMiddleware only
// honors it when RAILWAY_ENVIRONMENT != "production" — see backend/
// middleware/tenant.py). Harmless to send in production; the backend
// ignores it there.
const TENANT_SLUG = process.env.REACT_APP_TENANT_SLUG;

const client = axios.create({ baseURL: API_URL });

client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('elysium_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (TENANT_SLUG) config.headers['X-Tenant-Slug'] = TENANT_SLUG;
  return config;
});

export default client;
