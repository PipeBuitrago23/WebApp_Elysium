import client from './client';

export async function getMedicos() {
  const { data } = await client.get('/medicos/');
  return data;
}

export async function createMedico(body) {
  const { data } = await client.post('/medicos/', body);
  return data;
}
