import { useEffect, useState } from 'react';
import { Plus, Stethoscope, X } from 'lucide-react';
import { getMedicos, createMedico } from '../api/medicos';

const EMPTY_FORM = { email: '', password: '', nombre: '' };

export default function MedicosPage() {
  const [medicos, setMedicos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [modal,   setModal]   = useState(null);
  const [saving,  setSaving]  = useState(false);

  function fetchMedicos() {
    setLoading(true);
    setError('');
    getMedicos()
      .then(setMedicos)
      .catch(() => setError('Error al cargar los médicos.'))
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchMedicos(); }, []);

  function openCreate() {
    setModal({ form: { ...EMPTY_FORM }, formError: '' });
  }

  function handleFormChange(e) {
    const { name, value } = e.target;
    setModal((prev) => ({ ...prev, form: { ...prev.form, [name]: value } }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setModal((prev) => ({ ...prev, formError: '' }));
    try {
      await createMedico(modal.form);
      setModal(null);
      fetchMedicos();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al guardar.';
      setModal((prev) => ({ ...prev, formError: msg }));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-slate-500">
          Médicos externos en convenio que pueden remitir pacientes directamente a la agenda.
        </p>
        <button
          onClick={openCreate}
          className="flex items-center justify-center gap-2 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-all shrink-0"
        >
          <Plus className="w-4 h-4" />
          Nuevo médico
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="hidden md:table w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Nombre</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Email</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={2} className="text-center py-10 text-slate-400">Cargando…</td></tr>
            )}
            {!loading && medicos.length === 0 && (
              <tr><td colSpan={2} className="text-center py-10 text-slate-400">Aún no hay médicos registrados.</td></tr>
            )}
            {!loading && medicos.map((m) => (
              <tr key={m.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800 flex items-center gap-2">
                  <Stethoscope className="w-4 h-4 text-slate-400" />
                  {m.nombre}
                </td>
                <td className="px-4 py-3 text-slate-500">{m.email}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="md:hidden">
          {loading && <div className="text-center py-10 text-slate-400 text-sm">Cargando…</div>}
          {!loading && medicos.length === 0 && (
            <div className="text-center py-10 text-slate-400 text-sm">Aún no hay médicos registrados.</div>
          )}
          {!loading && medicos.map((m) => (
            <div key={m.id} className="px-4 py-3.5 border-b border-slate-100 last:border-0">
              <p className="font-semibold text-slate-800 text-sm flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-slate-400" />
                {m.nombre}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">{m.email}</p>
            </div>
          ))}
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-base font-semibold text-slate-800">Nuevo médico en convenio</h2>
              <button onClick={() => setModal(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              {modal.formError && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{modal.formError}</p>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Nombre completo</label>
                <input
                  type="text" name="nombre" value={modal.form.nombre} onChange={handleFormChange} required
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Correo electrónico</label>
                <input
                  type="email" name="email" value={modal.form.email} onChange={handleFormChange} required
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Contraseña</label>
                <input
                  type="password" name="password" value={modal.form.password} onChange={handleFormChange} required
                  minLength={6}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setModal(null)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-zinc-800 hover:bg-zinc-900 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-all"
                >
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
