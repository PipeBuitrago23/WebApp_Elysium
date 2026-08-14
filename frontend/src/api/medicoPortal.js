import client from './client';

export async function getMisCitas() {
  const { data } = await client.get('/medico/citas');
  return data;
}

export async function crearCitaMedico(body) {
  const { data } = await client.post('/medico/citas', body);
  return data;
}
