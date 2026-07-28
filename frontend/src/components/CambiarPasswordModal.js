import { useState } from 'react';
import { CheckCircle, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { cambiarPassword } from '../api/auth';

const EMPTY = { actual: '', nueva: '', confirmar: '' };

export default function CambiarPasswordModal({ onClose }) {
  const { token } = useAuth();
  const [form, setForm] = useState({ ...EMPTY });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (form.nueva.length < 6) { setError('La nueva contraseña debe tener al menos 6 caracteres.'); return; }
    if (form.nueva !== form.confirmar) { setError('Las contraseñas nuevas no coinciden.'); return; }
    setSaving(true);
    setError('');
    try {
      await cambiarPassword(token, form.actual, form.nueva);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al cambiar la contraseña.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Cambiar contraseña</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {success ? (
          <div className="px-6 py-8 text-center">
            <CheckCircle className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-800 mb-1">Contraseña actualizada</p>
            <p className="text-xs text-slate-400 mb-5">La usarás la próxima vez que inicies sesión.</p>
            <button
              onClick={onClose}
              className="px-5 py-2 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium rounded-lg transition-all"
            >
              Entendido
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Contraseña actual</label>
              <input
                type="password" name="actual" value={form.actual} onChange={handleChange} required
                autoComplete="current-password"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Nueva contraseña</label>
              <input
                type="password" name="nueva" value={form.nueva} onChange={handleChange} required minLength={6}
                autoComplete="new-password"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Confirmar nueva contraseña</label>
              <input
                type="password" name="confirmar" value={form.confirmar} onChange={handleChange} required minLength={6}
                autoComplete="new-password"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
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
        )}
      </div>
    </div>
  );
}
