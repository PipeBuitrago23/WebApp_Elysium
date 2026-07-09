import { useEffect, useMemo, useState } from 'react';
import { BarChart2, Calendar, CalendarDays, Clock, UserX, Users } from 'lucide-react';
import { getCitas } from '../api/citas';
import { getPacientes } from '../api/pacientes';
import { getPagos } from '../api/pagos';

// ── Constants ─────────────────────────────────────────────────────────────────

const DAYS_ES   = ['dom','lun','mar','mié','jue','vie','sáb'];
const MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

const ESTADO_STYLE = {
  programada:                    'bg-blue-100 text-blue-700',
  confirmada:                    'bg-zinc-100 text-zinc-700',
  completada:                    'bg-green-100 text-green-700',
  cancelada:                     'bg-slate-100 text-slate-500',
  'No asistió con penalización': 'bg-red-100 text-red-700',
};

const TIPO_STYLE = {
  Fisioterapia:         'bg-zinc-200 text-zinc-600',
  Pilates:              'bg-zinc-100 text-zinc-700',
  'Sesión de cortesía': 'bg-stone-100 text-stone-600',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function getMonday(d) {
  const date = new Date(d);
  const day  = date.getDay();
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

function fmtFecha(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return `${DAYS_ES[dt.getDay()]} ${d} ${MONTHS_ES[m - 1]}`;
}

function fmtHoy() {
  const d = new Date();
  return `${d.getDate()} ${MONTHS_ES[d.getMonth()]} ${d.getFullYear()}`;
}

function fmtMes() {
  const d   = new Date();
  const mes = MONTHS_ES[d.getMonth()];
  return `${mes.charAt(0).toUpperCase()}${mes.slice(1)} ${d.getFullYear()}`;
}

function countByTipo(citas) {
  const r = { Pilates: 0, Fisioterapia: 0, 'Sesión de cortesía': 0 };
  citas
    .filter((c) => c.estado !== 'cancelada')
    .forEach((c) => { if (c.tipo in r) r[c.tipo]++; });
  return r;
}

// ── Breakdown card ────────────────────────────────────────────────────────────

function BreakdownCard({ label, total, breakdown, sub, Icon, iconColor, iconBg, loading }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
            {label}
          </p>
          <p className="text-3xl font-bold text-slate-800">
            {loading ? <span className="text-slate-300">…</span> : total}
          </p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className={`p-2.5 rounded-lg shrink-0 ${iconBg}`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
      </div>

      <div className={`flex flex-wrap gap-4 pt-3 border-t border-slate-100 ${loading ? 'invisible' : ''}`}>
        <span className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="w-2 h-2 rounded-full bg-zinc-700 shrink-0" />
          Pilates <strong className="ml-0.5">{breakdown.Pilates}</strong>
        </span>
        <span className="flex items-center gap-1.5 text-xs text-slate-600">
          <span className="w-2 h-2 rounded-full bg-zinc-500 shrink-0" />
          Fisio <strong className="ml-0.5">{breakdown.Fisioterapia}</strong>
        </span>
        {breakdown['Sesión de cortesía'] > 0 && (
          <span className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="w-2 h-2 rounded-full bg-zinc-300 shrink-0" />
            Cortesía <strong className="ml-0.5">{breakdown['Sesión de cortesía']}</strong>
          </span>
        )}
      </div>
    </div>
  );
}

// ── Simple stat card ──────────────────────────────────────────────────────────

function StatCard({ label, value, sub, Icon, iconColor, iconBg, loading, warn }) {
  return (
    <div className={`bg-white rounded-xl border p-5 ${warn ? 'border-orange-300' : 'border-slate-200'}`}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
            {label}
          </p>
          <p className={`text-3xl font-bold ${warn ? 'text-orange-600' : 'text-slate-800'}`}>
            {loading ? <span className="text-slate-300">…</span> : value}
          </p>
          {sub && (
            <p className="text-xs text-slate-400 mt-1 truncate">
              {loading ? ' ' : sub}
            </p>
          )}
        </div>
        <div className={`p-2.5 rounded-lg shrink-0 ${iconBg}`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DashboardHome() {
  const [citasHoy, setCitasHoy]         = useState([]);
  const [citasSemana, setCitasSemana]   = useState([]);
  const [citasMes, setCitasMes]         = useState([]);
  const [citasRec, setCitasRec]         = useState([]);
  const [pacientesMap, setPacientesMap] = useState({});
  const [totalPacientes, setTotalPac]   = useState(0);
  const [pagos, setPagos]               = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');

  useEffect(() => {
    const ahora    = new Date();
    const hoy      = toISO(ahora);
    const lunes    = toISO(getMonday(ahora));
    const sabado   = toISO(addDays(getMonday(ahora), 5));
    const primer   = toISO(new Date(ahora.getFullYear(), ahora.getMonth(), 1));
    const ultimo   = toISO(new Date(ahora.getFullYear(), ahora.getMonth() + 1, 0));
    const hace10   = toISO(addDays(ahora, -10));

    Promise.all([
      getCitas({ fecha: hoy }),
      getCitas({ fecha_desde: lunes, fecha_hasta: sabado }),
      getCitas({ fecha_desde: primer, fecha_hasta: ultimo }),
      getCitas({ fecha_desde: hace10 }),
      getPacientes(),
      getPagos(),
    ])
      .then(([ch, cs, cm, cr, ps, pg]) => {
        setCitasHoy(ch.sort((a, b) => a.hora.localeCompare(b.hora)));
        setCitasSemana(cs);
        setCitasMes(cm);
        setCitasRec(cr);
        const map = {};
        ps.forEach((p) => { map[p.Paciente] = p.nombre; });
        setPacientesMap(map);
        setTotalPac(ps.length);
        setPagos(pg);
      })
      .catch(() => setError('Error al cargar los datos del dashboard.'))
      .finally(() => setLoading(false));
  }, []);

  const breakdownHoy    = useMemo(() => countByTipo(citasHoy),    [citasHoy]);
  const breakdownSemana = useMemo(() => countByTipo(citasSemana), [citasSemana]);
  const breakdownMes    = useMemo(() => countByTipo(citasMes),    [citasMes]);

  const countHoy    = citasHoy.filter((c) => c.estado !== 'cancelada').length;
  const countSemana = citasSemana.filter((c) => c.estado !== 'cancelada').length;
  const countMes    = citasMes.filter((c) => c.estado !== 'cancelada').length;

  const pacientesActivos = useMemo(() => {
    const hoy = toISO(new Date());
    const ids = new Set();
    pagos.forEach((p) => {
      if (p.sesiones_restantes > 0 && p.fecha_vencimiento >= hoy) ids.add(p.paciente_id);
    });
    return ids.size;
  }, [pagos]);

  // Patients who ever had a plan but have no non-cancelled appointment in last 10 days
  const pacientesInactivos = useMemo(() => {
    const conCitaReciente = new Set(
      citasRec.filter((c) => c.estado !== 'cancelada').map((c) => c.paciente_id),
    );
    const conPlan = new Set(pagos.map((p) => p.paciente_id));
    return [...conPlan].filter((id) => !conCitaReciente.has(id)).length;
  }, [citasRec, pagos]);

  const proximaCita = useMemo(() => {
    const ahora = new Date().toTimeString().slice(0, 5);
    return (
      citasHoy.find(
        (c) => ['programada', 'confirmada'].includes(c.estado) && c.hora.slice(0, 5) > ahora,
      ) || null
    );
  }, [citasHoy]);

  const citasHoySinCanceladas = citasHoy.filter((c) => c.estado !== 'cancelada');

  const cortesiasSemana = useMemo(() =>
    citasSemana
      .filter((c) => c.tipo === 'Sesión de cortesía' && c.estado !== 'cancelada')
      .sort((a, b) => a.fecha.localeCompare(b.fecha) || a.hora.localeCompare(b.hora)),
    [citasSemana],
  );

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Row 1 — breakdown cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <BreakdownCard
          label="Citas hoy"
          total={countHoy}
          breakdown={breakdownHoy}
          sub={fmtHoy()}
          Icon={Calendar}
          iconColor="text-zinc-600"
          iconBg="bg-zinc-100"
          loading={loading}
        />
        <BreakdownCard
          label="Esta semana"
          total={countSemana}
          breakdown={breakdownSemana}
          sub="Lun – Sáb"
          Icon={CalendarDays}
          iconColor="text-zinc-500"
          iconBg="bg-zinc-100"
          loading={loading}
        />
        <BreakdownCard
          label="Este mes"
          total={countMes}
          breakdown={breakdownMes}
          sub={fmtMes()}
          Icon={BarChart2}
          iconColor="text-zinc-400"
          iconBg="bg-zinc-100"
          loading={loading}
        />
      </div>

      {/* Row 2 — simple stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Pacientes activos"
          value={pacientesActivos}
          sub={`de ${totalPacientes} registrados`}
          Icon={Users}
          iconColor="text-zinc-600"
          iconBg="bg-zinc-100"
          loading={loading}
        />
        <StatCard
          label="Pacientes inactivos"
          value={pacientesInactivos}
          sub="+10 días sin cita"
          Icon={UserX}
          iconColor={!loading && pacientesInactivos > 0 ? 'text-orange-600' : 'text-zinc-400'}
          iconBg={!loading && pacientesInactivos > 0 ? 'bg-orange-50' : 'bg-zinc-100'}
          loading={loading}
          warn={!loading && pacientesInactivos > 0}
        />
        <StatCard
          label="Próxima cita hoy"
          value={proximaCita ? proximaCita.hora.slice(0, 5) : '–'}
          sub={
            proximaCita
              ? (pacientesMap[proximaCita.paciente_id] || proximaCita.paciente_id)
              : 'Sin más citas hoy'
          }
          Icon={Clock}
          iconColor="text-zinc-500"
          iconBg="bg-zinc-100"
          loading={loading}
        />
      </div>

      {/* Cortesías de la semana */}
      <div className="bg-white rounded-xl border border-amber-200 mb-4">
        <div className="px-6 py-4 border-b border-amber-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 shrink-0" />
            <h3 className="text-sm font-semibold text-slate-700">Sesiones de cortesía esta semana</h3>
          </div>
          <span className="text-xs text-slate-400">
            {loading ? '…' : `${cortesiasSemana.length} sesión${cortesiasSemana.length !== 1 ? 'es' : ''}`}
          </span>
        </div>

        {loading ? (
          <div className="px-6 py-8 text-center text-slate-400 text-sm">Cargando…</div>
        ) : cortesiasSemana.length === 0 ? (
          <div className="px-6 py-8 text-center text-slate-400 text-sm">
            Sin sesiones de cortesía agendadas esta semana.
          </div>
        ) : (
          <>
            {/* Desktop */}
            <table className="hidden md:table w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-400 uppercase tracking-wide">
                  <th className="px-6 py-3 text-left font-medium">Fecha</th>
                  <th className="px-6 py-3 text-left font-medium">Hora</th>
                  <th className="px-6 py-3 text-left font-medium">Paciente</th>
                  <th className="px-6 py-3 text-left font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {cortesiasSemana.map((c) => (
                  <tr key={c.id} className="border-b border-slate-50 last:border-0 hover:bg-amber-50/40 transition-colors">
                    <td className="px-6 py-3.5 text-slate-700 capitalize">{fmtFecha(c.fecha)}</td>
                    <td className="px-6 py-3.5 font-mono font-semibold text-slate-700">{c.hora.slice(0, 5)}</td>
                    <td className="px-6 py-3.5 text-slate-700">{pacientesMap[c.paciente_id] || c.paciente_id}</td>
                    <td className="px-6 py-3.5">
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                        {c.estado}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-slate-50">
              {cortesiasSemana.map((c) => (
                <div key={c.id} className="px-4 py-3.5 flex items-center gap-3">
                  <div className="shrink-0 text-center w-12">
                    <p className="font-bold font-mono text-slate-700 text-sm">{c.hora.slice(0, 5)}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5 capitalize leading-tight">
                      {fmtFecha(c.fecha).split(' ').slice(0, 2).join(' ')}
                    </p>
                  </div>
                  <div className="w-px h-8 bg-slate-100 shrink-0" />
                  <p className="flex-1 text-sm font-medium text-slate-700 truncate">
                    {pacientesMap[c.paciente_id] || c.paciente_id}
                  </p>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                    {c.estado}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Today's appointments table */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Citas de hoy</h3>
          <span className="text-xs text-slate-400">
            {loading ? '…' : `${countHoy} cita${countHoy !== 1 ? 's' : ''}`}
          </span>
        </div>

        {loading ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">Cargando…</div>
        ) : citasHoySinCanceladas.length === 0 ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">
            No hay citas programadas para hoy.
          </div>
        ) : (
          <>
            {/* Desktop */}
            <table className="hidden md:table w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs text-slate-400 uppercase tracking-wide">
                  <th className="px-6 py-3 text-left font-medium">Hora</th>
                  <th className="px-6 py-3 text-left font-medium">Paciente</th>
                  <th className="px-6 py-3 text-left font-medium">Tipo</th>
                  <th className="px-6 py-3 text-left font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {citasHoySinCanceladas.map((c) => (
                  <tr key={c.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors">
                    <td className="px-6 py-3.5 font-mono font-semibold text-slate-700">{c.hora.slice(0, 5)}</td>
                    <td className="px-6 py-3.5 text-slate-700">{pacientesMap[c.paciente_id] || c.paciente_id}</td>
                    <td className="px-6 py-3.5">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${TIPO_STYLE[c.tipo] || 'bg-slate-100 text-slate-600'}`}>
                        {c.tipo}
                      </span>
                    </td>
                    <td className="px-6 py-3.5">
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                        {c.estado}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-slate-50">
              {citasHoySinCanceladas.map((c) => (
                <div key={c.id} className="px-4 py-3.5 flex items-center gap-3">
                  <div className="w-12 shrink-0 text-center">
                    <p className="font-bold font-mono text-slate-700 text-sm">{c.hora.slice(0, 5)}</p>
                  </div>
                  <div className="w-px h-8 bg-slate-100 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">
                      {pacientesMap[c.paciente_id] || c.paciente_id}
                    </p>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded mt-1 inline-block ${TIPO_STYLE[c.tipo] || 'bg-slate-100 text-slate-600'}`}>
                      {c.tipo}
                    </span>
                  </div>
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${ESTADO_STYLE[c.estado] || 'bg-slate-100 text-slate-600'}`}>
                    {c.estado}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
