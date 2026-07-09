import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { getCitas, patchCitaEstado } from '../api/citas';
import { getPacientes } from '../api/pacientes';

// ── Constants ─────────────────────────────────────────────────────────────────

const SLOTS = [];
for (let h = 7; h <= 18; h++) {
  SLOTS.push(`${String(h).padStart(2, '0')}:00`);
  SLOTS.push(`${String(h).padStart(2, '0')}:30`);
}

const CAP = { Fisioterapia: 2, Pilates: 6, 'Sesión de cortesía': 6 };

const TIPO_STYLE = {
  Fisioterapia:         'bg-zinc-200 text-zinc-600',
  Pilates:              'bg-zinc-100 text-zinc-700',
  'Sesión de cortesía': 'bg-stone-100 text-stone-600',
};

const TIPO_CAP_COLOR = {
  Fisioterapia:         'text-zinc-500',
  Pilates:              'text-zinc-600',
  'Sesión de cortesía': 'text-stone-500',
};

const TIPO_SHORT = {
  Fisioterapia:         'Fisio',
  Pilates:              'Pilates',
  'Sesión de cortesía': 'Cortesía',
};

const ESTADO_STYLE = {
  programada:                    'bg-blue-100 text-blue-700',
  confirmada:                    'bg-zinc-100 text-zinc-700',
  completada:                    'bg-green-100 text-green-700',
  cancelada:                     'bg-slate-100 text-slate-600',
  'No asistió con penalización': 'bg-red-100 text-red-700',
};

const ESTADOS_TERMINAL = new Set(['completada', 'cancelada', 'No asistió con penalización']);

const DAYS_ES   = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
const MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

// ── Helpers ───────────────────────────────────────────────────────────────────

function getMonday(d) {
  const date = new Date(d);
  const day = date.getDay();
  date.setDate(date.getDate() + (day === 0 ? -6 : 1 - day));
  date.setHours(0, 0, 0, 0);
  return date;
}

function addDays(d, n) {
  const date = new Date(d);
  date.setDate(date.getDate() + n);
  return date;
}

function toISO(d) {
  const y   = d.getFullYear();
  const m   = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function fmtDateLabel(isoDate) {
  const [y, m, day] = isoDate.split('-').map(Number);
  const dt = new Date(y, m - 1, day);
  return `${DAYS_ES[dt.getDay()]} ${day} ${MONTHS_ES[m - 1]}`;
}

// ── Estado modal ──────────────────────────────────────────────────────────────

const ACCIONES = [
  {
    label:     'Confirmar',
    estado:    'confirmada',
    className: 'border border-slate-300 text-slate-700 hover:bg-slate-50',
    show:      (e) => e === 'programada',
  },
  {
    label:     'Completada',
    estado:    'completada',
    className: 'bg-green-600 hover:bg-green-700 text-white',
    show:      (e) => !ESTADOS_TERMINAL.has(e),
  },
  {
    label:     'No asistió',
    estado:    'No asistió con penalización',
    className: 'bg-red-600 hover:bg-red-700 text-white',
    show:      (e) => !ESTADOS_TERMINAL.has(e),
  },
  {
    label:     'Cancelar cita',
    estado:    'cancelada',
    className: 'bg-amber-500 hover:bg-amber-600 text-white',
    show:      (e) => !ESTADOS_TERMINAL.has(e),
  },
];

function EstadoModal({ cita, pacientesMap, onClose, onUpdate }) {
  const nombre = pacientesMap[cita.paciente_id] || cita.paciente_id;

  const [currentEstado, setCurrentEstado] = useState(cita.estado);
  const [saving, setSaving]               = useState(false);
  const [error, setError]                 = useState('');
  const [notice, setNotice]               = useState('');

  const isTerminal = ESTADOS_TERMINAL.has(currentEstado);

  async function cambiar(nuevoEstado) {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await patchCitaEstado(cita.id, nuevoEstado);
      setCurrentEstado(updated.estado);
      if (nuevoEstado === 'cancelada' && updated.estado !== 'cancelada') {
        setNotice(
          'Estaba dentro de la ventana de 2 horas: la cita fue marcada como "No asistió con penalización" y se descontó 1 sesión.',
        );
      }
      onUpdate();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al actualizar.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Gestionar cita</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Cita info */}
        <div className="px-5 pt-4 pb-3">
          <p className="font-semibold text-slate-800 text-sm">{nombre}</p>
          <p className="text-xs text-slate-500 mt-0.5">
            {fmtDateLabel(cita.fecha)} · {cita.hora.slice(0, 5)}
          </p>
          <span
            className={`mt-2 inline-block text-xs font-medium px-2 py-0.5 rounded ${TIPO_STYLE[cita.tipo] || 'bg-slate-100 text-slate-600'}`}
          >
            {cita.tipo}
          </span>
        </div>

        {/* Current estado */}
        <div className="px-5 pb-4">
          <p className="text-xs text-slate-400 mb-1">Estado actual</p>
          <span
            className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full ${ESTADO_STYLE[currentEstado] || 'bg-slate-100 text-slate-600'}`}
          >
            {currentEstado}
          </span>
        </div>

        {/* Actions */}
        <div className="px-5 pb-5">
          {isTerminal ? (
            <p className="text-sm text-slate-500 text-center py-2">
              Esta cita está en un estado final y no puede modificarse.
            </p>
          ) : (
            <>
              <p className="text-xs text-slate-400 mb-2">Cambiar a</p>
              <div className="flex flex-col gap-2">
                {ACCIONES.filter((a) => a.show(currentEstado)).map((a) => (
                  <button
                    key={a.estado}
                    onClick={() => cambiar(a.estado)}
                    disabled={saving}
                    className={`w-full py-2 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${a.className}`}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-[10px] text-slate-400 leading-snug">
                "Completada" y "No asistió" descuentan 1 sesión del plan activo.
                Cancelar dentro de 2 h aplica penalización automáticamente.
              </p>
            </>
          )}

          {notice && (
            <div className="mt-3 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700 leading-snug">
              {notice}
            </div>
          )}
          {error && (
            <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CitaChip({ cita, nombre, onClick }) {
  const isNoShow = cita.estado === 'No asistió con penalización';
  const chipStyle = isNoShow
    ? 'bg-red-100 text-red-700 border-red-200'
    : `${TIPO_STYLE[cita.tipo] || 'bg-slate-100 text-slate-600'} border-transparent`;

  return (
    <button
      onClick={() => onClick(cita)}
      className={`w-full text-left rounded px-1.5 py-1 leading-tight border hover:brightness-95 transition-all cursor-pointer ${chipStyle}`}
    >
      <div className="font-semibold truncate" style={{ maxWidth: 96 }}>
        {nombre || cita.paciente_id}
      </div>
      <div className="text-[10px] opacity-60">{TIPO_SHORT[cita.tipo] || cita.tipo}</div>
    </button>
  );
}

function CapacityBadges({ citas }) {
  const byTipo = {};
  citas.forEach((c) => { byTipo[c.tipo] = (byTipo[c.tipo] || 0) + 1; });
  return (
    <div className="flex gap-1 flex-wrap mt-1">
      {Object.entries(byTipo).map(([tipo, count]) => {
        const max = CAP[tipo] ?? '?';
        const full = count >= max;
        return (
          <span
            key={tipo}
            className={`text-[10px] font-bold ${full ? 'text-red-500' : (TIPO_CAP_COLOR[tipo] || 'text-slate-400')}`}
          >
            {count}/{max}
          </span>
        );
      })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AgendaPage() {
  const [weekStart, setWeekStart]       = useState(() => getMonday(new Date()));
  const [citas, setCitas]               = useState([]);
  const [pacientesMap, setPacientesMap] = useState({});
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState('');
  const [reloadTick, setReloadTick]     = useState(0);
  const [selectedCita, setSelectedCita] = useState(null);

  const days = useMemo(
    () => Array.from({ length: 6 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  );

  useEffect(() => {
    getPacientes()
      .then((list) => {
        const map = {};
        list.forEach((p) => { map[p.Paciente] = p.nombre; });
        setPacientesMap(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError('');
    getCitas({ fecha_desde: toISO(days[0]), fecha_hasta: toISO(days[5]) })
      .then(setCitas)
      .catch(() => setError('Error al cargar la agenda.'))
      .finally(() => setLoading(false));
  }, [days, reloadTick]);

  function slotCitas(date, slot) {
    return citas.filter(
      (c) =>
        c.fecha === toISO(date) &&
        c.hora.slice(0, 5) === slot &&
        c.estado !== 'cancelada',
    );
  }

  const todayISO  = toISO(new Date());
  const weekLabel = `${days[0].getDate()} ${MONTHS_ES[days[0].getMonth()]} – ${days[5].getDate()} ${MONTHS_ES[days[5].getMonth()]} ${days[5].getFullYear()}`;

  return (
    <div>
      {/* Navigation */}
      <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => setWeekStart((w) => addDays(w, -7))}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs sm:text-sm font-semibold text-slate-700 text-center min-w-0 sm:min-w-[200px]">
            {weekLabel}
          </span>
          <button
            onClick={() => setWeekStart((w) => addDays(w, 7))}
            className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <button
          onClick={() => setWeekStart(getMonday(new Date()))}
          className="text-xs text-zinc-600 hover:text-zinc-900 font-medium border border-zinc-200 px-3 py-1.5 rounded-lg hover:bg-zinc-50 transition-colors shrink-0"
        >
          Esta semana
        </button>
      </div>

      {/* Legend */}
      <div className="flex gap-2 mb-3 flex-wrap items-center">
        {Object.entries(TIPO_STYLE).map(([tipo, cls]) => (
          <span key={tipo} className={`text-xs font-medium px-2 py-0.5 rounded ${cls}`}>
            {TIPO_SHORT[tipo]}
          </span>
        ))}
        <span className="text-xs font-medium px-2 py-0.5 rounded bg-red-100 text-red-700">
          No asistió
        </span>
        <span className="text-xs text-slate-400 ml-1">· Click en cita para gestionar estado</span>
      </div>

      {error && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Grid */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-auto">
        <table className="w-full text-xs border-collapse" style={{ minWidth: 740 }}>
          <thead>
            <tr className="border-b border-slate-200 bg-white sticky top-0 z-10">
              <th className="w-14 px-3 py-3 text-left font-medium text-slate-400 bg-white">
                Hora
              </th>
              {days.map((d) => {
                const iso = toISO(d);
                const isToday = iso === todayISO;
                return (
                  <th
                    key={iso}
                    className={`px-2 py-3 text-center border-l border-slate-100 ${isToday ? 'bg-zinc-50' : 'bg-white'}`}
                  >
                    <div className={`text-[10px] uppercase tracking-wide font-medium ${isToday ? 'text-zinc-500' : 'text-slate-400'}`}>
                      {DAYS_ES[d.getDay()]}
                    </div>
                    <div className={`text-base font-bold leading-tight ${isToday ? 'text-zinc-700' : 'text-slate-700'}`}>
                      {d.getDate()}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-20 text-slate-400">
                  Cargando agenda…
                </td>
              </tr>
            ) : (
              SLOTS.map((slot) => {
                const hasAny = days.some((d) => slotCitas(d, slot).length > 0);
                return (
                  <tr
                    key={slot}
                    className={`border-b border-slate-100 last:border-0 transition-colors ${hasAny ? '' : 'hover:bg-slate-50/60'}`}
                  >
                    <td className="px-3 py-1.5 text-slate-400 font-mono align-top whitespace-nowrap pt-2">
                      {slot}
                    </td>
                    {days.map((d) => {
                      const iso = toISO(d);
                      const isToday = iso === todayISO;
                      const sc = slotCitas(d, slot);
                      return (
                        <td
                          key={iso}
                          className={`px-1.5 py-1 align-top border-l border-slate-100 ${isToday ? 'bg-zinc-50/50' : ''}`}
                          style={{ minWidth: 110 }}
                        >
                          {sc.length > 0 && (
                            <div className="space-y-1">
                              {sc.map((c) => (
                                <CitaChip
                                  key={c.id}
                                  cita={c}
                                  nombre={pacientesMap[c.paciente_id]}
                                  onClick={setSelectedCita}
                                />
                              ))}
                              <CapacityBadges citas={sc} />
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Estado modal */}
      {selectedCita && (
        <EstadoModal
          cita={selectedCita}
          pacientesMap={pacientesMap}
          onClose={() => setSelectedCita(null)}
          onUpdate={() => setReloadTick((t) => t + 1)}
        />
      )}
    </div>
  );
}
