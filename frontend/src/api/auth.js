import client from './client';

export async function loginRequest(email, password) {
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  const { data } = await client.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function aceptarHabeasData() {
  const { data } = await client.post('/auth/aceptar-habeas');
  return data;
}

export async function cambiarPassword(passwordActual, passwordNueva) {
  const { data } = await client.post('/auth/cambiar-password', {
    password_actual: passwordActual,
    password_nueva: passwordNueva,
  });
  return data;
}
