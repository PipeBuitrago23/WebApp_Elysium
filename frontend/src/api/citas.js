import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getCitas({ fecha, fecha_desde, fecha_hasta, paciente_id, estado } = {}) {
  const params = {};
  if (fecha) params.fecha = fecha;
  if (fecha_desde) params.fecha_desde = fecha_desde;
  if (fecha_hasta) params.fecha_hasta = fecha_hasta;
  if (paciente_id) params.paciente_id = paciente_id;
  if (estado) params.estado = estado;
  const { data } = await axios.get(`${API_URL}/citas/`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function getCita(id) {
  const { data } = await axios.get(`${API_URL}/citas/${id}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function createCita(body) {
  const { data } = await axios.post(`${API_URL}/citas/`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function updateCita(id, body) {
  const { data } = await axios.put(`${API_URL}/citas/${id}`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function deleteCita(id) {
  await axios.delete(`${API_URL}/citas/${id}`, {
    headers: authHeaders(),
  });
}

export async function patchCitaEstado(id, estado) {
  const { data } = await axios.patch(
    `${API_URL}/citas/${id}/estado`,
    { estado },
    { headers: authHeaders() },
  );
  return data;
}
