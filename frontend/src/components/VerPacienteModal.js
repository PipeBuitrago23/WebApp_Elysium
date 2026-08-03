import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { getCitas } from '../api/citas';
import { getPagos } from '../api/pagos';

const MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

const PAQUETE_STYLE = {
  Pilates:      'bg-zinc-100 text-zinc-700',
  Fisioterapia: 'bg-zinc-200 text-zinc-600',
};

const TIPO_STYLE = {
  Fisioterapia:         'bg-zinc-200 text-zinc-600',
  Pilates:              'bg-zinc-100 text-zinc-700',
  'Sesión de cortesía': 'bg-stone-100 text-stone-600',
};

const ESTADO_STYLE = {
  programada:                    'bg-blue-100 text-blue-700',
  confirmada:                    'bg-zinc-100 text-zinc-700',
  completada:                    'bg-green-100 text-green-700',
  cancelada:                     'bg-slate-100 text-slate-500',
  'No asistió con penalización': 'bg-red-100 text-red-700',
};

function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${parseInt(d)} ${MONTHS_ES[parseInt(m) - 1]} ${y}`;
}

function venceColor(iso) {
  const today = new Date().toISOString().split('T')[0];
  const diff = Math.ceil((new Date(iso) - new Date(today)) / 86400000);
  if (diff < 0)  return 'text-red-600 font-semibold';
  if (diff <= 7) return 'text-amber-600 font-semibold';
  return 'text-green-700';
}

function InfoField({ label, value }) {
  return (
    <div>
      <p className="text-xs text-slate-400 uppercase tracking-wide mb-0.5">{label}</p>
      <p className="text-sm text-slate-700">{value || '—'}</p>
    </div>
  );
}

export default function VerPacienteModal({ paciente, onClose, onEdit }) {
  const [citas, setCitas] = useState([]);
  const [pagos, setPagos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      getCitas({ paciente_id: paciente.Paciente }),
      getPagos(paciente.Paciente),
    ])
      .then(([c, p]) => {
        setCitas([...c].sort((a, b) => (b.fecha + b.hora).localeCompare(a.fecha + a.hora)));
        setPagos(p);
      })
      .catch(() => setError('Error al cargar la información del paciente.'))
      .finally(() => setLoading(false));
  }, [paciente.Paciente]);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <div>
            <h2 className="text-base font-semibold text-slate-800">{paciente.nombre}</h2>
            <p className="text-xs text-slate-400 font-mono mt-0.5">{paciente.Paciente}</p>
          </div>
          <div className="flex items-center gap-2">
            {onEdit && (
              <button
                onClick={onEdit}
                className="px-3 py-1.5 text-xs font-medium text-zinc-700 border border-zinc-200 rounded-lg hover:bg-zinc-50 transition-colors"
              >
                Editar
              </button>
            )}
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Datos personales */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Datos del paciente</p>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <InfoField label="Teléfono" value={paciente.telefono} />
              <InfoField label="Email" value={paciente.email} />
              <InfoField label="Fecha de nacimiento" value={fmtDate(paciente.fecha_nacimiento)} />
            </div>
            <div className="space-y-3">
              <InfoField label="Antecedentes relevantes" value={paciente.antecedentes} />
              <InfoField label="Cirugías / procedimientos" value={paciente.cirugias} />
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
          )}

          {/* Registro de planes */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Registro de planes {!loading && `(${pagos.length})`}
            </p>
            {loading ? (
              <p className="text-sm text-slate-400">Cargando…</p>
            ) : pagos.length === 0 ? (
              <p className="text-sm text-slate-400">Sin planes registrados.</p>
            ) : (
              <div className="space-y-2">
                {pagos.map((p) => (
                  <div key={p.id} className="flex flex-wrap items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${PAQUETE_STYLE[p.tipo_paquete] || 'bg-slate-100 text-slate-600'}`}>
                      {p.tipo_paquete}
                    </span>
                    <span className="text-sm text-slate-700 tabular-nums">
                      {p.sesiones_restantes} / {p.total_sesiones} sesiones
                    </span>
                    <span className="text-xs text-slate-400">Pagado {fmtDate(p.fecha_pago)}</span>
                    <span className={`text-xs ml-auto ${venceColor(p.fecha_vencimiento)}`}>
                      Vence {fmtDate(p.fecha_vencimiento)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Registro de citas */}
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
              Registro de citas {!loading && `(${citas.length})`}
            </p>
            {loading ? (
              <p className="text-sm text-slate-400">Cargando…</p>
            ) : citas.length === 0 ? (
              <p className="text-sm text-slate-400">Sin citas registradas.</p>
            ) : (
              <div className="space-y-2">
                {citas.map((c) => (
                  <div key={c.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-sm font-medium text-slate-700">{fmtDate(c.fecha)}</span>
                      <span className="text-sm font-mono text-slate-500">{c.hora.slice(0, 5)}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${TIPO_STYLE[c.tipo] || 'bg-slate-100 text-slate-600'}`}>
                        {c.tipo}
                      </span>
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ml-auto ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                        {c.estado}
                      </span>
                    </div>
                    {(c.medico_nombre || c.notas) && (
                      <div className="mt-2 pt-2 border-t border-slate-200 text-xs text-slate-500 space-y-0.5">
                        {c.medico_nombre && (
                          <p>Remitido por: <span className="font-medium text-slate-600">{c.medico_nombre}</span>{c.motivo_remision ? ` — ${c.motivo_remision}` : ''}</p>
                        )}
                        {c.notas && <p>Notas: {c.notas}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
