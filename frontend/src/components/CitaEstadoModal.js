import { useState } from 'react';
import { X } from 'lucide-react';
import { patchCitaEstado, ajusteAdminCita } from '../api/citas';
import { useTenant } from '../context/TenantContext';
import { buildSlots } from '../utils/schedule';

const TIPO_STYLE = {
  Fisioterapia:         'bg-zinc-200 text-zinc-600',
  Pilates:              'bg-zinc-100 text-zinc-700',
  'Sesión de cortesía': 'bg-stone-100 text-stone-600',
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

function fmtDateLabel(isoDate) {
  const [y, m, day] = isoDate.split('-').map(Number);
  const dt = new Date(y, m - 1, day);
  return `${DAYS_ES[dt.getDay()]} ${day} ${MONTHS_ES[m - 1]}`;
}

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
];

// Modal para gestionar el estado de una cita — confirmar/completada/no
// asistió (descuentan sesión), reagendar/cancelar sin descontar. Compartido
// entre AgendaPage.js (vista semanal) y DashboardHome.js (tabla "Citas de
// hoy"), para no duplicar esta lógica en dos lugares.
export default function CitaEstadoModal({ cita, pacientesMap, onClose, onUpdate }) {
  const { horario } = useTenant();
  const slots = buildSlots(horario);
  const nombre = pacientesMap[cita.paciente_id] || cita.paciente_id;

  const [currentEstado, setCurrentEstado] = useState(cita.estado);
  const [saving, setSaving]               = useState(false);
  const [error, setError]                 = useState('');
  const [ajusteMode, setAjusteMode]       = useState(null);  // null | 'reprogramar'
  const [ajusteFecha, setAjusteFecha]     = useState('');
  const [ajusteHora, setAjusteHora]       = useState('');
  const [ajusteSaving, setAjusteSaving]   = useState(false);
  const [ajusteError, setAjusteError]     = useState('');

  const isTerminal = ESTADOS_TERMINAL.has(currentEstado);

  async function cambiar(nuevoEstado) {
    setSaving(true);
    setError('');
    try {
      const updated = await patchCitaEstado(cita.id, nuevoEstado);
      setCurrentEstado(updated.estado);
      onUpdate();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al actualizar.');
    } finally {
      setSaving(false);
    }
  }

  async function cancelarSinDescuento() {
    setAjusteSaving(true);
    setAjusteError('');
    try {
      const updated = await ajusteAdminCita(cita.id, { accion: 'cancelar' });
      setCurrentEstado(updated.estado);
      onUpdate();
    } catch (err) {
      setAjusteError(err.response?.data?.detail || 'Error al cancelar.');
    } finally {
      setAjusteSaving(false);
    }
  }

  async function reprogramarSinDescuento() {
    setAjusteSaving(true);
    setAjusteError('');
    try {
      const updated = await ajusteAdminCita(cita.id, {
        accion: 'reprogramar',
        fecha: ajusteFecha,
        hora: ajusteHora + ':00',
      });
      setCurrentEstado(updated.estado);
      setAjusteMode(null);
      onUpdate();
    } catch (err) {
      setAjusteError(err.response?.data?.detail || 'Error al reprogramar.');
    } finally {
      setAjusteSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-y-auto max-h-[90vh]">
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
          <p className="text-xs text-slate-400 mt-2">
            Médico remitente: <span className="text-slate-600 font-medium">{cita.medico_nombre || 'Directo'}</span>
          </p>
          {cita.motivo_remision && (
            <p className="text-xs text-slate-400 mt-1 leading-snug">{cita.motivo_remision}</p>
          )}
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
              {/* Standard attendance / status actions */}
              <p className="text-xs text-slate-400 mb-2">Cambiar a</p>
              <div className="flex flex-col gap-2">
                {ACCIONES.filter((a) => a.show(currentEstado)).map((a) => (
                  <button
                    key={a.estado}
                    onClick={() => cambiar(a.estado)}
                    disabled={saving || ajusteSaving}
                    className={`w-full py-2 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${a.className}`}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
              <p className="mt-3 text-[10px] text-slate-400 leading-snug">
                "Completada" y "No asistió" descuentan 1 sesión del plan activo
                — usa "No asistió" también para cancelaciones tardías que
                deban penalizarse.
              </p>

              {/* Cancel / reschedule — no session deduction */}
              <div className="mt-4 pt-4 border-t border-slate-100">
                <p className="text-xs text-slate-400 mb-2 font-medium">Cancelar o reagendar (sin afectar sesiones)</p>
                {ajusteMode !== 'reprogramar' ? (
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={cancelarSinDescuento}
                      disabled={saving || ajusteSaving}
                      className="w-full py-2 px-4 rounded-lg text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      {ajusteSaving ? 'Cancelando…' : 'Cancelar cita'}
                    </button>
                    <button
                      onClick={() => { setAjusteMode('reprogramar'); setAjusteError(''); }}
                      disabled={saving || ajusteSaving}
                      className="w-full py-2 px-4 rounded-lg text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
                    >
                      Cambiar horario
                    </button>
                    {ajusteError && (
                      <div className="p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                        {ajusteError}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <input
                      type="date"
                      value={ajusteFecha}
                      onChange={(e) => setAjusteFecha(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-zinc-300"
                    />
                    <select
                      value={ajusteHora}
                      onChange={(e) => setAjusteHora(e.target.value)}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-zinc-300"
                    >
                      <option value="">Seleccionar hora</option>
                      {slots.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                    {ajusteError && (
                      <div className="p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                        {ajusteError}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={reprogramarSinDescuento}
                        disabled={ajusteSaving || !ajusteFecha || !ajusteHora}
                        className="flex-1 py-2 px-4 rounded-lg text-sm font-medium bg-zinc-800 text-white hover:bg-zinc-900 transition-colors disabled:opacity-50"
                      >
                        {ajusteSaving ? 'Guardando…' : 'Guardar'}
                      </button>
                      <button
                        onClick={() => { setAjusteMode(null); setAjusteError(''); }}
                        className="flex-1 py-2 px-4 rounded-lg text-sm font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                      >
                        Atrás
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
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
