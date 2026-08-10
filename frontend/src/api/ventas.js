import client from './client';

export async function getVentas(params = {}) {
  const { data } = await client.get('/ventas/', { params });
  return data;
}

export async function createVenta(body) {
  const { data } = await client.post('/ventas/', body);
  return data;
}

export async function deleteVenta(id) {
  await client.delete(`/ventas/${id}`);
}
