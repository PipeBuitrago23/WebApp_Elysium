import client from './client';

export async function getGastos(params = {}) {
  const { data } = await client.get('/gastos/', { params });
  return data;
}

export async function createGasto(body) {
  const { data } = await client.post('/gastos/', body);
  return data;
}

export async function deleteGasto(id) {
  await client.delete(`/gastos/${id}`);
}
