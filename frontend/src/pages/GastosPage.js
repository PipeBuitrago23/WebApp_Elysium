import { useEffect, useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';
import { getGastos, createGasto, deleteGasto } from '../api/gastos';
import { METODOS_PAGO } from '../constants/packages';

// ── Helpers ───────────────────────────────────────────────────────────────────

function localDateISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function cop(v) {
  return `$${Number(v).toLocaleString('es-CO')}`;
}

const MONTHS = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

const EMPTY_FORM = {
  nombre:      '',
  nit:         '',
  valor:       '',
  fecha:       localDateISO(),
  metodo_pago: '',
  descripcion: '',
};

// ── Modal ─────────────────────────────────────────────────────────────────────

function NuevoGastoModal({ onClose, onCreated }) {
  const [form, setForm]     = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  function setField(key, val) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const body = {
        nombre:      form.nombre,
        nit:         form.nit || null,
        valor:       parseFloat(form.valor),
        fecha:       form.fecha,
        metodo_pago: form.metodo_pago,
        descripcion: form.descripcion || null,
      };
      const nuevo = await createGasto(body);
      onCreated(nuevo);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar el gasto.');
    } finally {
      setSaving(false);
    }
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-zinc-300';
  const labelCls = 'block text-xs font-medium text-slate-500 mb-1';

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-y-auto max-h-[90vh]">
        <div className="bg-zinc-950 px-6 py-4 rounded-t-2xl flex items-center justify-between">
          <p className="text-white text-sm font-medium tracking-wide">Nuevo Gasto</p>
          <button onClick={onClose} className="text-zinc-400 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <div>
            <label className={labelCls}>Concepto *</label>
            <input
              type="text"
              required
              placeholder="Ej: Alquiler estudio, Equipo Pilates…"
              value={form.nombre}
              onChange={(e) => setField('nombre', e.target.value)}
              className={inputCls}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>NIT proveedor</label>
              <input
                type="text"
                placeholder="Opcional"
                value={form.nit}
                onChange={(e) => setField('nit', e.target.value)}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Valor (COP) *</label>
              <input
                type="number"
                min="1"
                required
                value={form.valor}
                onChange={(e) => setField('valor', e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Método de pago *</label>
              <select
                required
                value={form.metodo_pago}
                onChange={(e) => setField('metodo_pago', e.target.value)}
                className={inputCls}
              >
                <option value="">Seleccionar…</option>
                {METODOS_PAGO.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Fecha *</label>
              <input
                type="date"
                required
                value={form.fecha}
                onChange={(e) => setField('fecha', e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          <div>
            <label className={labelCls}>Descripción / observaciones</label>
            <textarea
              rows={3}
              placeholder="Opcional…"
              value={form.descripcion}
              onChange={(e) => setField('descripcion', e.target.value)}
              className={`${inputCls} resize-none`}
            />
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2.5 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'Guardando…' : 'Registrar gasto'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border border-slate-200 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function GastosPage() {
  const [gastos,   setGastos]   = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [modal,    setModal]    = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    getGastos()
      .then(setGastos)
      .catch(() => setError('Error al cargar gastos.'))
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(nuevo) {
    setGastos((g) => [nuevo, ...g]);
  }

  async function handleDelete(id) {
    try {
      await deleteGasto(id);
      setGastos((g) => g.filter((x) => x.id !== id));
    } catch {
      setError('Error al eliminar el gasto.');
    } finally {
      setDeletingId(null);
    }
  }

  const totalMes = gastos
    .filter((g) => {
      const d = new Date();
      const [y, m] = g.fecha.split('-').map(Number);
      return y === d.getFullYear() && m === d.getMonth() + 1;
    })
    .reduce((acc, g) => acc + g.valor, 0);

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Total gastos registrados</p>
          <p className="text-3xl font-bold text-slate-800">{loading ? '…' : gastos.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Gastos este mes</p>
          <p className="text-3xl font-bold text-slate-800">{loading ? '…' : cop(totalMes)}</p>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Registro de gastos</h3>
          <button
            onClick={() => setModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={15} />
            Nuevo gasto
          </button>
        </div>

        {loading ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">Cargando…</div>
        ) : gastos.length === 0 ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">
            No hay gastos registrados aún.
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs text-slate-400 uppercase tracking-wide">
                    <th className="px-6 py-3 text-left font-medium">Fecha</th>
                    <th className="px-6 py-3 text-left font-medium">Concepto</th>
                    <th className="px-6 py-3 text-left font-medium">NIT</th>
                    <th className="px-6 py-3 text-left font-medium">Valor</th>
                    <th className="px-6 py-3 text-left font-medium">Método</th>
                    <th className="px-6 py-3 text-left font-medium">Descripción</th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {gastos.map((g) => (
                    <tr key={g.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-3.5 text-slate-500 text-xs">{fmtDate(g.fecha)}</td>
                      <td className="px-6 py-3.5 text-slate-700 font-medium">{g.nombre}</td>
                      <td className="px-6 py-3.5 text-slate-400 text-xs">{g.nit || '—'}</td>
                      <td className="px-6 py-3.5 text-slate-700 font-mono text-xs font-semibold">{cop(g.valor)}</td>
                      <td className="px-6 py-3.5 text-slate-500 text-xs">{g.metodo_pago}</td>
                      <td className="px-6 py-3.5 text-slate-400 text-xs max-w-[200px] truncate">{g.descripcion || '—'}</td>
                      <td className="px-6 py-3.5 text-right">
                        {deletingId === g.id ? (
                          <div className="flex items-center justify-end gap-2">
                            <span className="text-xs text-slate-500">¿Eliminar?</span>
                            <button onClick={() => handleDelete(g.id)} className="text-xs text-red-600 font-semibold hover:underline">Sí</button>
                            <button onClick={() => setDeletingId(null)} className="text-xs text-slate-400 hover:underline">No</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeletingId(g.id)}
                            className="p-1.5 text-slate-300 hover:text-red-500 transition-colors rounded"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile */}
            <div className="md:hidden divide-y divide-slate-50">
              {gastos.map((g) => (
                <div key={g.id} className="px-4 py-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{g.nombre}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{fmtDate(g.fecha)} · {g.metodo_pago}</p>
                    </div>
                    <p className="text-sm font-mono font-bold text-slate-700">{cop(g.valor)}</p>
                  </div>
                  {g.descripcion && <p className="text-xs text-slate-400 mt-1">{g.descripcion}</p>}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {modal && (
        <NuevoGastoModal
          onClose={() => setModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
