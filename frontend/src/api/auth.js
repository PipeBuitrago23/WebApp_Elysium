import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export async function loginRequest(email, password) {
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  const { data } = await axios.post(`${API_URL}/auth/login`, form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function aceptarHabeasData(token) {
  const { data } = await axios.post(
    `${API_URL}/auth/aceptar-habeas`,
    {},
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return data;
}
