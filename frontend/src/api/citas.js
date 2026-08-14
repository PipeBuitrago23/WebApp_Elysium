import client from './client';

export async function getCitas({ fecha, fecha_desde, fecha_hasta, paciente_id, estado } = {}) {
  const params = {};
  if (fecha) params.fecha = fecha;
  if (fecha_desde) params.fecha_desde = fecha_desde;
  if (fecha_hasta) params.fecha_hasta = fecha_hasta;
  if (paciente_id) params.paciente_id = paciente_id;
  if (estado) params.estado = estado;
  const { data } = await client.get('/citas/', { params });
  return data;
}

export async function getCita(id) {
  const { data } = await client.get(`/citas/${id}`);
  return data;
}

export async function createCita(body) {
  const { data } = await client.post('/citas/', body);
  return data;
}

export async function updateCita(id, body) {
  const { data } = await client.put(`/citas/${id}`, body);
  return data;
}

export async function deleteCita(id) {
  await client.delete(`/citas/${id}`);
}

export async function patchCitaEstado(id, estado) {
  const { data } = await client.patch(`/citas/${id}/estado`, { estado });
  return data;
}

export async function ajusteAdminCita(id, body) {
  const { data } = await client.patch(`/citas/${id}/ajuste-admin`, body);
  return data;
}
