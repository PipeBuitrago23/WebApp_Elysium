import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getMisCitas() {
  const { data } = await axios.get(`${API_URL}/medico/citas`, {
    headers: authHeaders(),
  });
  return data;
}

export async function crearCitaMedico(body) {
  const { data } = await axios.post(`${API_URL}/medico/citas`, body, {
    headers: authHeaders(),
  });
  return data;
}
