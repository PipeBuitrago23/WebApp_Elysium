import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getVentas(params = {}) {
  const { data } = await axios.get(`${API_URL}/ventas/`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function createVenta(body) {
  const { data } = await axios.post(`${API_URL}/ventas/`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function deleteVenta(id) {
  await axios.delete(`${API_URL}/ventas/${id}`, {
    headers: authHeaders(),
  });
}
