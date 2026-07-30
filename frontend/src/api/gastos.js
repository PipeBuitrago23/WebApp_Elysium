import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getGastos(params = {}) {
  const { data } = await axios.get(`${API_URL}/gastos/`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function createGasto(body) {
  const { data } = await axios.post(`${API_URL}/gastos/`, body, {
    headers: authHeaders(),
  });
  return data;
}

export async function deleteGasto(id) {
  await axios.delete(`${API_URL}/gastos/${id}`, {
    headers: authHeaders(),
  });
}
