import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function authHeaders() {
  const token = sessionStorage.getItem('elysium_token');
  return { Authorization: `Bearer ${token}` };
}

export async function getPagos(paciente_id) {
  const params = paciente_id ? { paciente_id } : {};
  const { data } = await axios.get(`${API_URL}/pagos/`, {
    headers: authHeaders(),
    params,
  });
  return data;
}

export async function createPago(body) {
  const { data } = await axios.post(`${API_URL}/pagos/`, body, {
    headers: authHeaders(),
  });
  return data;
}
