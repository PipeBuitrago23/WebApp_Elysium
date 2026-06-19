const stats = [
  { label: 'Citas hoy',     value: '—' },
  { label: 'Esta semana',   value: '—' },
  { label: 'Pacientes',     value: '—' },
  { label: 'Próxima cita',  value: '—' },
];

export default function DashboardHome() {
  return (
    <div>
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-5">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">{s.label}</p>
            <p className="text-3xl font-bold text-slate-800">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Today's appointments */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Citas de hoy</h3>
          <span className="text-xs text-slate-400">0 citas</span>
        </div>
        <div className="px-6 py-14 text-center">
          <p className="text-slate-400 text-sm">No hay citas programadas para hoy.</p>
        </div>
      </div>
    </div>
  );
}
