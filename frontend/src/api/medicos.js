import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getMedicos() {
  const { data } = await axios.get(`${API_URL}/medicos/`, {
    headers: authHeaders(),
  });
  return data;
}

export async function createMedico(body) {
  const { data } = await axios.post(`${API_URL}/medicos/`, body, {
    headers: authHeaders(),
  });
  return data;
}
