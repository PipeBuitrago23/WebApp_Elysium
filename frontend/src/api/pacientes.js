import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = localStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getPacientes(q = '') {
  const params = q ? { q } : {};
  const { data } = await axios.get(`${API_URL}/pacientes/`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function getPaciente(id) {
  const { data } = await axios.get(`${API_URL}/pacientes/${id}`, {
    headers: authHeaders(),
  });
  return data;
}

export async function createPaciente(body) {
  const { data } = await axios.post(`${API_URL}/pacientes/`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function updatePaciente(id, body) {
  const { data } = await axios.put(`${API_URL}/pacientes/${id}`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function deletePaciente(id) {
  await axios.delete(`${API_URL}/pacientes/${id}`, {
    headers: authHeaders(),
  });
}
