import client from './client';

export async function getTenantConfig() {
  const { data } = await client.get('/tenant/config');
  return data;
}
