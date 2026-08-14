import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, LogOut, Stethoscope } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTenant } from '../context/TenantContext';
import { buildSlots } from '../utils/schedule';
import { getMisCitas, crearCitaMedico } from '../api/medicoPortal';

// ── Constants ─────────────────────────────────────────────────────────────────

const ESTADO_STYLE = {
  programada:                    'bg-blue-100 text-blue-700',
  confirmada:                    'bg-zinc-100 text-zinc-700',
  completada:                    'bg-green-100 text-green-700',
  cancelada:                     'bg-slate-100 text-slate-500',
  'No asistió con penalización': 'bg-red-100 text-red-700',
};

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const EMPTY = { cedula: '', nombre: '', telefono: '', email: '', fecha: today(), hora: '', tipo: '', motivo_remision: '' };

// ── Helpers ───────────────────────────────────────────────────────────────────

const MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

function fmtFecha(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS_ES[m - 1]} ${y}`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MisCitas({ citas, loading, error }) {
  if (loading) return <div className="text-center py-14 text-slate-400 text-sm">Cargando…</div>;
  if (error) return <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>;
  if (citas.length === 0) {
    return (
      <div className="text-center py-14 text-slate-400 text-sm">
        Aún no has remitido pacientes. Usa la pestaña "Agendar nuevo paciente".
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      {/* Desktop */}
      <table className="hidden md:table w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 bg-slate-50">
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Fecha</th>
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Hora</th>
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Paciente</th>
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Tipo</th>
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Estado</th>
            <th className="text-left px-4 py-3 font-semibold text-slate-600">Comentarios</th>
          </tr>
        </thead>
        <tbody>
          {citas.map((c) => (
            <tr key={c.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-4 py-3 text-slate-700">{fmtFecha(c.fecha)}</td>
              <td className="px-4 py-3 font-mono text-slate-700">{c.hora.slice(0, 5)}</td>
              <td className="px-4 py-3 font-medium text-slate-800">{c.paciente_nombre}</td>
              <td className="px-4 py-3 text-slate-500">{c.tipo}</td>
              <td className="px-4 py-3">
                <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                  {c.estado}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-500 max-w-xs truncate">{c.motivo_remision || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile */}
      <div className="md:hidden">
        {citas.map((c) => (
          <div key={c.id} className="px-4 py-3.5 border-b border-slate-100 last:border-0">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-slate-800 text-sm">{c.paciente_nombre}</p>
                <p className="text-xs text-slate-400 mt-0.5">{fmtFecha(c.fecha)} · {c.hora.slice(0, 5)}</p>
              </div>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                {c.estado}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-2">{c.tipo}</p>
            {c.motivo_remision && <p className="text-xs text-slate-400 mt-1">{c.motivo_remision}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function MedicoPortalPage() {
  const { user, logout } = useAuth();
  const { tenant, servicios, horario } = useTenant();
  const TIPOS = servicios.map((s) => s.nombre);
  const VALID_SLOTS = buildSlots(horario);
  const navigate = useNavigate();
  const [tab, setTab] = useState('citas');

  const [citas, setCitas] = useState([]);
  const [loadingCitas, setLoadingCitas] = useState(true);
  const [citasError, setCitasError] = useState('');

  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  function loadCitas() {
    setLoadingCitas(true);
    setCitasError('');
    getMisCitas()
      .then(setCitas)
      .catch(() => setCitasError('Error al cargar tus pacientes.'))
      .finally(() => setLoadingCitas(false));
  }

  useEffect(() => { loadCitas(); }, []);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.cedula.trim()) { setError('Ingresa la cédula del paciente.'); return; }
    if (!form.nombre.trim()) { setError('Ingresa el nombre del paciente.'); return; }
    if (!form.tipo) { setError('Selecciona el tipo de servicio.'); return; }
    if (!form.hora) { setError('Selecciona la hora.'); return; }
    setSaving(true);
    setError('');
    try {
      const cita = await crearCitaMedico({
        cedula: form.cedula.trim(),
        nombre: form.nombre.trim(),
        telefono: form.telefono || undefined,
        email: form.email || undefined,
        fecha: form.fecha,
        hora: form.hora + ':00',
        tipo: form.tipo,
        motivo_remision: form.motivo_remision || undefined,
      });
      setSuccess(cita);
      setForm({ ...EMPTY, fecha: form.fecha });
      loadCitas();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar la cita.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Branding header */}
      <div className="bg-zinc-950 py-5 px-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="text-center flex-1">
            <h1 className="text-lg font-light tracking-widest uppercase text-white">{tenant.nombre_comercial}</h1>
            <p className="text-[10px] text-zinc-400 uppercase tracking-widest mt-1">Portal Médico en Convenio</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors shrink-0"
          >
            <LogOut size={14} />
            Salir
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6">
        <div className="flex items-center gap-2 mb-5">
          <Stethoscope className="w-5 h-5 text-zinc-500" />
          <p className="text-sm text-slate-600">
            Dr(a). <span className="font-semibold text-slate-800">{user?.nombre}</span>
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-5">
          <button
            onClick={() => setTab('citas')}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              tab === 'citas' ? 'bg-zinc-800 text-white border-zinc-800' : 'bg-white text-slate-600 border-slate-200 hover:border-zinc-400'
            }`}
          >
            Mis pacientes / citas
          </button>
          <button
            onClick={() => { setTab('agendar'); setSuccess(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
              tab === 'agendar' ? 'bg-zinc-800 text-white border-zinc-800' : 'bg-white text-slate-600 border-slate-200 hover:border-zinc-400'
            }`}
          >
            Agendar nuevo paciente
          </button>
        </div>

        {tab === 'citas' && (
          <MisCitas citas={citas} loading={loadingCitas} error={citasError} />
        )}

        {tab === 'agendar' && (
          success ? (
            <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center max-w-lg mx-auto">
              <CheckCircle className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
              <h2 className="text-lg font-semibold text-slate-800 mb-1">Cita registrada</h2>
              <p className="text-sm text-slate-500 mb-0.5 font-medium">{success.paciente_nombre}</p>
              <p className="text-sm text-slate-400 mb-6">
                {fmtFecha(success.fecha)} · {success.hora.slice(0, 5)} · {success.tipo}
              </p>
              <button
                onClick={() => setSuccess(null)}
                className="bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium px-5 py-2 rounded-lg transition-all"
              >
                Agendar otro paciente
              </button>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden max-w-lg mx-auto">
              <div className="px-6 py-4 border-b border-slate-100">
                <h2 className="text-base font-semibold text-slate-800">Agendar nuevo paciente</h2>
                <p className="text-xs text-slate-400 mt-0.5">Si la cédula ya está registrada, se usará ese perfil</p>
              </div>

              <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
                {error && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Cédula</label>
                    <input
                      type="text" name="cedula" value={form.cedula} onChange={handleChange} required
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Nombre completo</label>
                    <input
                      type="text" name="nombre" value={form.nombre} onChange={handleChange} required
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Teléfono <span className="text-slate-400 font-normal">(opcional)</span></label>
                    <input
                      type="text" name="telefono" value={form.telefono} onChange={handleChange}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">Email <span className="text-slate-400 font-normal">(opcional)</span></label>
                    <input
                      type="email" name="email" value={form.email} onChange={handleChange}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Fecha</label>
                  <input
                    type="date" name="fecha" value={form.fecha} min={today()} onChange={handleChange} required
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-2">Tipo de servicio</label>
                  <div className="flex gap-2 flex-wrap">
                    {TIPOS.map((t) => (
                      <button
                        key={t} type="button" onClick={() => setForm((f) => ({ ...f, tipo: t }))}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                          form.tipo === t ? 'bg-zinc-800 text-white border-zinc-800' : 'bg-white text-slate-600 border-slate-200 hover:border-zinc-400'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Hora</label>
                  <select
                    name="hora" value={form.hora} onChange={handleChange} required
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 bg-white"
                  >
                    <option value="">Selecciona un horario…</option>
                    {VALID_SLOTS.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    Motivo de remisión <span className="text-slate-400 font-normal">(opcional)</span>
                  </label>
                  <textarea
                    name="motivo_remision" value={form.motivo_remision} onChange={handleChange} rows={3}
                    placeholder="Ej. Dolor lumbar post-quirúrgico, requiere fisioterapia de rehabilitación…"
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 resize-none"
                  />
                </div>

                <div className="pt-1">
                  <button
                    type="submit" disabled={saving}
                    className="w-full bg-zinc-800 hover:bg-zinc-900 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-all"
                  >
                    {saving ? 'Guardando…' : 'Registrar cita'}
                  </button>
                </div>
              </form>
            </div>
          )
        )}
      </div>
    </div>
  );
}
