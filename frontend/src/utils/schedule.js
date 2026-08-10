// Replaces the identical 7-11/14-18-every-30-min generation loop that used
// to be copy-pasted in NuevaCitaPage.js, AgendaPage.js, and PortalPage.js —
// now built from the tenant's own horario.bloques/intervalo_min instead of
// a hardcoded window.
export function buildSlots(horario) {
  if (!horario?.bloques?.length) return [];
  const intervalo = horario.intervalo_min || 30;
  const slots = [];

  for (const { inicio, fin } of horario.bloques) {
    let [h, m] = inicio.split(':').map(Number);
    const [hf, mf] = fin.split(':').map(Number);

    while (h < hf || (h === hf && m <= mf)) {
      slots.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
      m += intervalo;
      if (m >= 60) {
        h += Math.floor(m / 60);
        m %= 60;
      }
    }
  }

  return slots;
}
