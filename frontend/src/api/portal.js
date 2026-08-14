import client from './client';

export async function getPortalPaciente(cedula) {
  const { data } = await client.get(`/portal/paciente/${cedula}`);
  return data;
}

export async function portalRegistro(body) {
  const { data } = await client.post('/portal/registro', body);
  return data;
}

export async function portalCrearCita(body) {
  const { data } = await client.post('/portal/citas', body);
  return data;
}

export async function portalCrearCitaRecurrente(body) {
  const { data } = await client.post('/portal/citas/recurrente', body);
  return data;
}

export async function portalCancelarCita(citaId, pacienteId) {
  const { data } = await client.post(`/portal/citas/${citaId}/cancelar`, {
    paciente_id: pacienteId,
  });
  return data;
}

export async function portalReprogramarCita(citaId, pacienteId, fecha, hora) {
  const { data } = await client.post(`/portal/citas/${citaId}/reprogramar`, {
    paciente_id: pacienteId,
    fecha,
    hora,
  });
  return data;
}
