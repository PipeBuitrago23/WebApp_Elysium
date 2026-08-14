import client from './client';

export async function getPagos(paciente_id) {
  const params = paciente_id ? { paciente_id } : {};
  const { data } = await client.get('/pagos/', { params });
  return data;
}

export async function createPago(body) {
  const { data } = await client.post('/pagos/', body);
  return data;
}
