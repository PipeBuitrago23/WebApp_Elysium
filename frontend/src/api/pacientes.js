import client from './client';

export async function getPacientes(q = '') {
  const params = q ? { q } : {};
  const { data } = await client.get('/pacientes/', { params });
  return data;
}

export async function getPaciente(id) {
  const { data } = await client.get(`/pacientes/${id}`);
  return data;
}

export async function createPaciente(body) {
  const { data } = await client.post('/pacientes/', body);
  return data;
}

export async function updatePaciente(id, body) {
  const { data } = await client.put(`/pacientes/${id}`, body);
  return data;
}

export async function deletePaciente(id, force = false) {
  await client.delete(`/pacientes/${id}`, {
    params: force ? { force: true } : {},
  });
}
