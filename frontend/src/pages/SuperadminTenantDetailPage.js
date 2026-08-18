import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getTenant, updateTenant } from '../api/superadmin';

function errorMsg(e) {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(' · ');
  }
  return detail || 'Ocurrió un error.';
}

const pretty = (obj) => JSON.stringify(obj ?? {}, null, 2);

export default function SuperadminTenantDetailPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [plan, setPlan] = useState('basico');
  const [estado, setEstado] = useState('activo');
  const [brandingText, setBrandingText] = useState('{}');
  const [configText, setConfigText] = useState('{}');
  const [featuresText, setFeaturesText] = useState('{}');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  const cargar = async () => {
    setLoading(true);
    try {
      const t = await getTenant(slug);
      setTenant(t);
      setPlan(t.plan);
      setEstado(t.estado);
      setBrandingText(pretty(t.branding));
      setConfigText(pretty(t.config));
      setFeaturesText(pretty(t.features_override));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const handleGuardar = async () => {
    setError('');
    setOk('');
    // Parse de los JSON antes de armar el payload — un JSON inválido aborta.
    let branding, config, features;
    try { branding = JSON.parse(brandingText); } catch { return setError('branding: JSON inválido'); }
    try { config = JSON.parse(configText); } catch { return setError('config: JSON inválido'); }
    try { features = JSON.parse(featuresText); } catch { return setError('features_override: JSON inválido'); }

    // Solo se envían los campos que cambiaron (PATCH parcial).
    const payload = {};
    if (plan !== tenant.plan) payload.plan = plan;
    if (estado !== tenant.estado) payload.estado = estado;
    if (JSON.stringify(branding) !== JSON.stringify(tenant.branding)) payload.branding = branding;
    if (JSON.stringify(config) !== JSON.stringify(tenant.config)) payload.config = config;
    if (JSON.stringify(features) !== JSON.stringify(tenant.features_override)) payload.features_override = features;

    if (Object.keys(payload).length === 0) return setOk('Sin cambios.');

    setSaving(true);
    try {
      const updated = await updateTenant(slug, payload);
      setTenant(updated);
      setBrandingText(pretty(updated.branding));
      setConfigText(pretty(updated.config));
      setFeaturesText(pretty(updated.features_override));
      setOk('Cambios guardados.');
    } catch (err) {
      setError(errorMsg(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400">Cargando…</div>;
  if (!tenant) return null;

  const ta = 'w-full font-mono text-xs border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-zinc-500';

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-zinc-950 text-white">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <button onClick={() => navigate('/superadmin')} className="text-xs text-zinc-400 hover:text-white">← Tenants</button>
          <div className="text-right">
            <p className="text-[10px] text-zinc-500 uppercase tracking-[0.3em]">{tenant.slug}</p>
            <h1 className="text-lg font-light">{tenant.nombre_comercial}</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {error && <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm">{error}</div>}
        {ok && <div className="px-4 py-3 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-700 text-sm">{ok}</div>}

        {/* Plan + estado */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Plan</label>
            <select value={plan} onChange={(e) => setPlan(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-500">
              <option value="basico">basico</option>
              <option value="completo">completo</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Estado</label>
            <select value={estado} onChange={(e) => setEstado(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-500">
              <option value="trial">trial</option>
              <option value="activo">activo</option>
              <option value="suspendido">suspendido</option>
            </select>
          </div>
        </div>

        {/* Servicios (solo lectura) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Servicios</p>
          <div className="space-y-1.5">
            {tenant.servicios.map((s) => (
              <div key={s.nombre} className="flex items-center gap-3 text-sm text-slate-700">
                <span className="font-medium w-32">{s.nombre}</span>
                <span className="text-slate-500">cap. {s.capacidad}</span>
                <span className="text-slate-500">· {s.duracion_min} min</span>
                {!s.activo && <span className="text-red-500 text-xs">(inactivo)</span>}
              </div>
            ))}
          </div>
        </div>

        {/* JSON: branding / config / features_override */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">branding</label>
            <textarea rows={4} value={brandingText} onChange={(e) => setBrandingText(e.target.value)} className={ta} />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">config (horario, vigencia_plan_dias, ventana_cancelacion_horas, sesion_cortesia)</label>
            <textarea rows={10} value={configText} onChange={(e) => setConfigText(e.target.value)} className={ta} />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">features_override (ej. {'{"habilitadas": ["ventas"]}'})</label>
            <textarea rows={3} value={featuresText} onChange={(e) => setFeaturesText(e.target.value)} className={ta} />
          </div>
        </div>

        <div className="flex justify-end">
          <button onClick={handleGuardar} disabled={saving}
            className="bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium rounded-lg px-5 py-2.5 transition disabled:opacity-60">
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </main>
    </div>
  );
}
