import superadminClient from './superadminClient';

export async function superadminLogin(email, password) {
  // El backend usa OAuth2PasswordRequestForm → form-urlencoded (username/password).
  const body = new URLSearchParams({ username: email, password });
  const { data } = await superadminClient.post('/superadmin/auth/login', body);
  return data;
}

export async function getTenants() {
  const { data } = await superadminClient.get('/superadmin/tenants/');
  return data;
}

export async function getTenant(slug) {
  const { data } = await superadminClient.get(`/superadmin/tenants/${slug}`);
  return data;
}

export async function createTenant(payload) {
  const { data } = await superadminClient.post('/superadmin/tenants/', payload);
  return data;
}

export async function updateTenant(slug, payload) {
  const { data } = await superadminClient.patch(`/superadmin/tenants/${slug}`, payload);
  return data;
}
