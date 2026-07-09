import axios from 'axios';

const BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export async function getPortalPaciente(cedula) {
  const { data } = await axios.get(`${BASE}/portal/paciente/${cedula}`);
  return data;
}

export async function portalRegistro(body) {
  const { data } = await axios.post(`${BASE}/portal/registro`, body);
  return data;
}

export async function portalCrearCita(body) {
  const { data } = await axios.post(`${BASE}/portal/citas`, body);
  return data;
}

export async function portalCancelarCita(citaId, pacienteId) {
  const { data } = await axios.post(`${BASE}/portal/citas/${citaId}/cancelar`, {
    paciente_id: pacienteId,
  });
  return data;
}

export async function portalReprogramarCita(citaId, pacienteId, fecha, hora) {
  const { data } = await axios.post(`${BASE}/portal/citas/${citaId}/reprogramar`, {
    paciente_id: pacienteId,
    fecha,
    hora,
  });
  return data;
}
