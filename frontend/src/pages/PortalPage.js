import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getPortalPaciente, portalCrearCita, portalRegistro } from '../api/portal';

// ── Constants ─────────────────────────────────────────────────────────────────

const DAYS_ES   = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MONTHS_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

const VALID_SLOTS = [];
for (let h = 7; h <= 18; h++) {
  VALID_SLOTS.push(`${String(h).padStart(2, '0')}:00`);
  VALID_SLOTS.push(`${String(h).padStart(2, '0')}:30`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function toISO(d) {
  const y   = d.getFullYear();
  const m   = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function fmtFecha(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return `${DAYS_ES[dt.getDay()]} ${d} ${MONTHS_ES[m - 1]}`;
}

function diasHastaVencimiento(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const target = new Date(y, m - 1, d);
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return Math.ceil((target - hoy) / (1000 * 60 * 60 * 24));
}

// ── Sub-components ────────────────────────────────────────────────────────────

const ESTADO_BADGE = {
  programada: 'bg-blue-100 text-blue-700',
  confirmada: 'bg-zinc-100 text-zinc-700',
};

function PlanCard({ plan }) {
  const pct       = Math.round((plan.sesiones_restantes / plan.total_sesiones) * 100);
  const dias      = diasHastaVencimiento(plan.fecha_vencimiento);
  const barColor  = pct > 50 ? 'bg-zinc-700' : pct > 25 ? 'bg-amber-400' : 'bg-red-500';
  const daysColor = dias > 14 ? 'text-emerald-600' : dias > 7 ? 'text-amber-600' : 'text-red-600';
  const daysLabel = dias > 1 ? `${dias} días` : dias === 1 ? '1 día' : dias === 0 ? 'hoy' : 'vencido';

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wide font-medium mb-0.5">Plan activo</p>
          <p className="font-bold text-slate-800">{plan.tipo_paquete}</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-700">
          activo
        </span>
      </div>

      <div className="mb-3">
        <div className="flex justify-between items-center text-sm mb-1.5">
          <span className="text-slate-500">Sesiones restantes</span>
          <span className="font-bold text-slate-800">
            {plan.sesiones_restantes} de {plan.total_sesiones}
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5">
          <div
            className={`h-2.5 rounded-full transition-all duration-500 ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-sm">
        <span className="text-slate-400">Vence:</span>
        <span className={`font-semibold ${daysColor}`}>
          {fmtFecha(plan.fecha_vencimiento)} · {daysLabel}
        </span>
      </div>
    </div>
  );
}

function CitaCard({ cita }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
      <div className="text-center w-14 shrink-0">
        <p className="text-lg font-bold text-slate-800 leading-none">{cita.hora.slice(0, 5)}</p>
        <p className="text-[10px] text-slate-400 mt-0.5 uppercase">hora</p>
      </div>
      <div className="w-px h-10 bg-slate-100 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="font-medium text-slate-700 text-sm">{cita.tipo}</p>
        <p className="text-xs text-slate-400 mt-0.5">{fmtFecha(cita.fecha)}</p>
      </div>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
        ESTADO_BADGE[cita.estado] || 'bg-slate-100 text-slate-500'
      }`}>
        {cita.estado}
      </span>
    </div>
  );
}

function BookingForm({ pacienteId, sinPlan, onSuccess, onCancel }) {
  const [form, setForm]       = useState(() => ({ tipo: sinPlan ? 'Sesión de cortesía' : 'Pilates', fecha: '', hora: '' }));
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.fecha || !form.hora) {
      setError('Selecciona la fecha y la hora.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await portalCrearCita({
        paciente_id: pacienteId,
        fecha: form.fecha,
        hora: `${form.hora}:00`,
        tipo: form.tipo,
      });
      onSuccess(`Cita de ${form.tipo} reservada para el ${fmtFecha(form.fecha)} a las ${form.hora}.`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al reservar. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
      <h3 className="font-semibold text-slate-700 mb-4 text-sm">Nueva cita</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        {sinPlan ? (
          <div className="flex items-center gap-2 py-2">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">Tipo:</span>
            <span className="bg-zinc-100 text-zinc-700 text-sm font-semibold px-3 py-1 rounded-full">
              Sesión de cortesía
            </span>
          </div>
        ) : (
          <div>
            <label className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-2 block">
              Tipo
            </label>
            <div className="flex gap-2">
              {['Pilates', 'Fisioterapia'].map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, tipo: t }))}
                  className={`flex-1 py-2.5 px-3 rounded-xl text-sm font-medium border transition-all ${
                    form.tipo === t
                      ? 'bg-zinc-800 text-white border-zinc-800'
                      : 'border-slate-200 text-slate-600 hover:border-zinc-400 bg-white'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}

        <div>
          <label className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1.5 block">
            Fecha
          </label>
          <input
            type="date"
            value={form.fecha}
            min={toISO(new Date())}
            onChange={(e) => setForm((f) => ({ ...f, fecha: e.target.value }))}
            className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="text-xs text-slate-500 font-medium uppercase tracking-wide mb-1.5 block">
            Hora
          </label>
          <select
            value={form.hora}
            onChange={(e) => setForm((f) => ({ ...f, hora: e.target.value }))}
            className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-800 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
          >
            <option value="">Selecciona la hora</option>
            {VALID_SLOTS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 py-3 rounded-xl border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex-1 py-3 rounded-xl bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-semibold transition-all disabled:opacity-50"
          >
            {loading ? 'Reservando…' : 'Confirmar reserva'}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PortalPage() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // True when a patient is logged in via email/password (not anonymous QR access)
  const isAuthPatient = isAuthenticated && !!user?.paciente_id;

  const [cedula, setCedula]           = useState('');
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState('');
  const [paciente, setPaciente]       = useState(null);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [successMsg, setSuccessMsg]   = useState('');

  // Registration form state
  const [showRegister, setShowRegister] = useState(false);
  const [regForm, setRegForm]           = useState({ nombre: '', cedula: '', telefono: '' });
  const [regLoading, setRegLoading]     = useState(false);
  const [regError, setRegError]         = useState('');

  // Auto-load patient data for authenticated sessions (skip cedula form)
  useEffect(() => {
    if (isAuthPatient) {
      setLoading(true);
      getPortalPaciente(user.paciente_id)
        .then(setPaciente)
        .catch(() => setError('No se pudo cargar tu información.'))
        .finally(() => setLoading(false));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function buscar(e) {
    e.preventDefault();
    const id = cedula.trim();
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      const data = await getPortalPaciente(id);
      setPaciente(data);
      setSuccessMsg('');
      setBookingOpen(false);
    } catch (err) {
      setError(
        err.response?.status === 404
          ? 'No encontramos un paciente con esa cédula.'
          : 'Error al buscar. Intenta de nuevo.',
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleBookingSuccess(msg) {
    setBookingOpen(false);
    setSuccessMsg(msg);
    try {
      const id = paciente.paciente_id;
      const data = await getPortalPaciente(id);
      setPaciente(data);
    } catch {
      // stale data acceptable — cita was created
    }
  }

  async function handleRegistro(e) {
    e.preventDefault();
    setRegLoading(true);
    setRegError('');
    try {
      const data = await portalRegistro(regForm);
      setPaciente(data);
      setSuccessMsg('¡Bienvenido! Tu perfil fue creado. El equipo completará tu ficha cuando asistas a tu primera sesión.');
      setShowRegister(false);
    } catch (err) {
      setRegError(err.response?.data?.detail || 'Error al crear el perfil. Intenta de nuevo.');
    } finally {
      setRegLoading(false);
    }
  }

  function handleSalir() {
    if (isAuthPatient) {
      logout();
      navigate('/login');
    } else {
      setPaciente(null);
      setCedula('');
      setSuccessMsg('');
      setBookingOpen(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Branding header */}
      <div className="bg-zinc-950 py-5 text-center">
        <h1 className="text-lg font-light tracking-widest uppercase text-white">Elysium</h1>
        <p className="text-[10px] text-zinc-400 uppercase tracking-widest mt-1">
          Fisioterapia & Pilates
        </p>
      </div>

      <div className="max-w-md mx-auto px-4 py-8">

        {/* ── Auth patient: loading spinner while auto-fetching ── */}
        {isAuthPatient && !paciente && loading && (
          <div className="text-center text-slate-400 py-20 text-sm">Cargando tu información…</div>
        )}

        {/* ── Anonymous: cedula entry ── */}
        {!isAuthPatient && !paciente && !showRegister && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
            <h2 className="text-2xl font-bold text-slate-800 mb-1 text-center">Bienvenido</h2>
            <p className="text-slate-500 text-sm text-center mb-6">
              Ingresa tu número de cédula para ver tu plan y reservar citas
            </p>
            <form onSubmit={buscar} className="space-y-4">
              <input
                type="text"
                inputMode="numeric"
                value={cedula}
                onChange={(e) => setCedula(e.target.value)}
                placeholder="Número de cédula"
                className="w-full border border-slate-200 rounded-xl px-4 py-3.5 text-slate-800 text-center text-xl tracking-widest focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={loading || !cedula.trim()}
                className="w-full bg-zinc-800 hover:bg-zinc-900 text-white font-semibold py-3.5 rounded-xl transition-all disabled:opacity-50 text-base"
              >
                {loading ? 'Buscando…' : 'Ingresar'}
              </button>
            </form>
            {error && (
              <p className="text-red-600 text-sm text-center mt-4">{error}</p>
            )}
            <div className="mt-6 pt-5 border-t border-slate-100 text-center">
              <p className="text-slate-400 text-xs mb-2">¿Primera vez en Elysium?</p>
              <button
                onClick={() => { setShowRegister(true); setError(''); }}
                className="text-zinc-600 hover:text-zinc-900 text-sm font-medium underline underline-offset-2"
              >
                Crea tu perfil aquí
              </button>
            </div>
          </div>
        )}

        {/* ── Anonymous: registration form ── */}
        {!isAuthPatient && !paciente && showRegister && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
            <h2 className="text-2xl font-bold text-slate-800 mb-1">Nuevo paciente</h2>
            <p className="text-slate-500 text-sm mb-6">
              Solo necesitamos 3 datos. El equipo completará tu ficha cuando asistas a tu primera sesión.
            </p>
            <form onSubmit={handleRegistro} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
                  Nombre completo
                </label>
                <input
                  type="text"
                  value={regForm.nombre}
                  onChange={(e) => setRegForm((f) => ({ ...f, nombre: e.target.value }))}
                  placeholder="Ej. María García"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
                  Número de cédula
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={regForm.cedula}
                  onChange={(e) => setRegForm((f) => ({ ...f, cedula: e.target.value }))}
                  placeholder="Ej. 1234567890"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1.5">
                  Teléfono / WhatsApp
                </label>
                <input
                  type="tel"
                  inputMode="tel"
                  value={regForm.telefono}
                  onChange={(e) => setRegForm((f) => ({ ...f, telefono: e.target.value }))}
                  placeholder="Ej. 3001234567"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:border-transparent"
                />
              </div>
              {regError && (
                <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-red-700 text-sm">
                  {regError}
                </div>
              )}
              <button
                type="submit"
                disabled={regLoading || !regForm.nombre.trim() || !regForm.cedula.trim() || !regForm.telefono.trim()}
                className="w-full bg-zinc-800 hover:bg-zinc-900 text-white font-semibold py-3.5 rounded-xl transition-all disabled:opacity-50 text-base"
              >
                {regLoading ? 'Creando perfil…' : 'Crear mi perfil'}
              </button>
            </form>
            <div className="mt-5 pt-4 border-t border-slate-100 text-center">
              <button
                onClick={() => { setShowRegister(false); setRegError(''); setRegForm({ nombre: '', cedula: '', telefono: '' }); }}
                className="text-slate-400 hover:text-slate-600 text-sm"
              >
                Ya tengo un perfil → Ingresar con cédula
              </button>
            </div>
          </div>
        )}

        {/* ── Patient dashboard ── */}
        {paciente && (
          <div className="space-y-4">
            {/* Greeting row */}
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-800 leading-tight">{paciente.nombre}</h2>
                <p className="text-slate-400 text-sm mt-0.5">Cédula {paciente.paciente_id}</p>
              </div>
              <button
                onClick={handleSalir}
                className="text-xs text-slate-400 hover:text-slate-600 border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors shrink-0 ml-3 mt-1"
              >
                {isAuthPatient ? 'Cerrar sesión' : 'Cambiar'}
              </button>
            </div>

            {/* Success banner */}
            {successMsg && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-green-700 text-sm">
                {successMsg}
              </div>
            )}

            {/* Error banner (auth auto-load failures) */}
            {error && !paciente && (
              <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Plan */}
            {paciente.plan_activo ? (
              <PlanCard plan={paciente.plan_activo} />
            ) : (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-center">
                <p className="font-semibold text-amber-800 mb-1">Sin plan activo</p>
                <p className="text-amber-600 text-sm">
                  Puedes agendar tu Sesión de cortesía. Cuando asistas, el equipo de Elysium te asignará un plan.
                </p>
              </div>
            )}

            {/* Upcoming citas */}
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                Próximas citas
              </h3>
              {paciente.citas_proximas.length > 0 ? (
                <div className="space-y-2">
                  {paciente.citas_proximas.map((c) => (
                    <CitaCard key={c.id} cita={c} />
                  ))}
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-slate-400 text-sm">
                  No tienes citas próximas agendadas.
                </div>
              )}
            </div>

            {/* Booking section */}
            <div>
              {!bookingOpen ? (
                <button
                  onClick={() => { setBookingOpen(true); setSuccessMsg(''); }}
                  className="w-full py-3.5 bg-zinc-800 hover:bg-zinc-900 text-white font-semibold rounded-xl transition-all"
                >
                  {paciente.plan_activo ? 'Reservar nueva cita' : 'Agendar Sesión de cortesía'}
                </button>
              ) : (
                <BookingForm
                  pacienteId={paciente.paciente_id}
                  sinPlan={!paciente.plan_activo}
                  onSuccess={handleBookingSuccess}
                  onCancel={() => setBookingOpen(false)}
                />
              )}
            </div>

            <p className="text-xs text-slate-300 text-center pt-2">
              Elysium Fisio-Pilates · Portal del Paciente
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
