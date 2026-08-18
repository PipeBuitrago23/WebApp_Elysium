import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSuperadminAuth } from '../context/SuperadminAuthContext';
import { getTenants, createTenant } from '../api/superadmin';

const PLAN_BADGE = {
  completo: 'bg-zinc-800 text-white',
  basico: 'bg-slate-200 text-slate-700',
};
const ESTADO_BADGE = {
  activo: 'bg-emerald-100 text-emerald-700',
  trial: 'bg-blue-100 text-blue-700',
  suspendido: 'bg-red-100 text-red-700',
};

const EMPTY_FORM = { slug: '', nombre: '', plan: 'basico', admin_email: '', admin_nombre: '' };

function fmtFecha(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function errorMsg(e) {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(' · ');
  }
  return detail || 'Ocurrió un error.';
}

export default function SuperadminTenantsPage() {
  const { logout } = useSuperadminAuth();
  const navigate = useNavigate();
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [creado, setCreado] = useState(null); // { slug, admin_email, admin_password_temporal }

  const cargar = async () => {
    setLoading(true);
    try {
      setTenants(await getTenants());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const abrirModal = () => {
    setForm(EMPTY_FORM);
    setFormError('');
    setCreado(null);
    setModalOpen(true);
  };

  const handleCrear = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const res = await createTenant(form);
      setCreado(res);
      await cargar();
    } catch (err) {
      setFormError(errorMsg(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top bar */}
      <header className="bg-zinc-950 text-white">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] text-zinc-500 uppercase tracking-[0.3em]">Plataforma</p>
            <h1 className="text-lg font-light tracking-widest uppercase">Panel Superadmin</h1>
          </div>
          <button
            onClick={() => { logout(); navigate('/superadmin/login'); }}
            className="text-xs text-zinc-400 hover:text-white border border-zinc-700 rounded-lg px-3 py-1.5 transition"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-semibold text-slate-800">Tenants</h2>
          <button
            onClick={abrirModal}
            className="bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
          >
            + Nuevo tenant
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Slug</th>
                <th className="text-left px-4 py-3 font-medium">Nombre comercial</th>
                <th className="text-left px-4 py-3 font-medium">Plan</th>
                <th className="text-left px-4 py-3 font-medium">Estado</th>
                <th className="text-left px-4 py-3 font-medium">Alta</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} className="text-center py-10 text-slate-400">Cargando…</td></tr>
              )}
              {!loading && tenants.length === 0 && (
                <tr><td colSpan={5} className="text-center py-10 text-slate-400">No hay tenants.</td></tr>
              )}
              {!loading && tenants.map((t) => (
                <tr
                  key={t.slug}
                  onClick={() => navigate(`/superadmin/tenants/${t.slug}`)}
                  className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{t.slug}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{t.nombre_comercial}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${PLAN_BADGE[t.plan] || 'bg-slate-100 text-slate-600'}`}>{t.plan}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ESTADO_BADGE[t.estado] || 'bg-slate-100 text-slate-600'}`}>{t.estado}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{fmtFecha(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>

      {/* Create modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">Nuevo tenant</h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>

            {creado ? (
              <div className="px-6 py-6">
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 mb-4">
                  <p className="text-emerald-800 font-semibold text-sm mb-2">✓ Tenant «{creado.slug}» creado.</p>
                  <p className="text-slate-600 text-sm mb-1">Admin: <span className="font-mono">{creado.admin_email}</span></p>
                  <p className="text-slate-600 text-sm">Contraseña temporal:</p>
                  <p className="font-mono text-base bg-white border border-emerald-200 rounded-lg px-3 py-2 mt-1 select-all">
                    {creado.admin_password_temporal}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-2">Guárdala ahora — no se vuelve a mostrar.</p>
                </div>
                <button
                  onClick={() => setModalOpen(false)}
                  className="w-full py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-900 text-white font-medium text-sm transition"
                >
                  Listo
                </button>
              </div>
            ) : (
              <form onSubmit={handleCrear} className="px-6 py-5 space-y-3">
                {formError && (
                  <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm">{formError}</div>
                )}
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Slug (subdominio)</label>
                  <input
                    value={form.slug}
                    onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                    required placeholder="pilates-med"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Nombre comercial</label>
                  <input
                    value={form.nombre}
                    onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
                    required placeholder="Pilates Medellín"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Plan</label>
                  <select
                    value={form.plan}
                    onChange={(e) => setForm((f) => ({ ...f, plan: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  >
                    <option value="basico">basico</option>
                    <option value="completo">completo</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Email del admin</label>
                  <input
                    type="email"
                    value={form.admin_email}
                    onChange={(e) => setForm((f) => ({ ...f, admin_email: e.target.value }))}
                    required placeholder="admin@pilatesmed.com"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Nombre del admin</label>
                  <input
                    value={form.admin_nombre}
                    onChange={(e) => setForm((f) => ({ ...f, admin_nombre: e.target.value }))}
                    required placeholder="Ana Ruiz"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  />
                </div>
                <button
                  type="submit"
                  disabled={saving}
                  className="w-full py-2.5 mt-1 rounded-lg bg-zinc-800 hover:bg-zinc-900 text-white font-medium text-sm transition disabled:opacity-60"
                >
                  {saving ? 'Creando…' : 'Crear tenant'}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
