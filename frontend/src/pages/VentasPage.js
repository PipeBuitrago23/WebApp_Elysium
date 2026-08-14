import { useEffect, useState } from 'react';
import { Plus, Trash2, X } from 'lucide-react';
import { getPacientes } from '../api/pacientes';
import { getVentas, createVenta, deleteVenta } from '../api/ventas';
import { CATEGORIAS, METODOS_PAGO, PACKAGES } from '../constants/packages';

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
  paciente_id:    '',
  categoria:      '',
  nombre_paquete: '',
  total_sesiones: '',
  valor_total:    '',
  estado_pago:    'pago', // 'pago' | 'abono' | 'pendiente'
  abono:          '',
  metodo_pago:    '',
  fecha_inicio:   localDateISO(),
  fecha_pago:     localDateISO(),
};

// ── Badge ─────────────────────────────────────────────────────────────────────

function EstadoBadge({ estado }) {
  const cls =
    estado === 'pagada'
      ? 'bg-green-100 text-green-700'
      : 'bg-amber-100 text-amber-700';
  return (
    <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${cls}`}>
      {estado === 'pagada' ? 'Pagada' : 'Pendiente'}
    </span>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function NuevaVentaModal({ pacientes, onClose, onCreated }) {
  const [form, setForm]     = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');
  const [search, setSearch] = useState('');

  const paquetes  = PACKAGES[form.categoria] || [];
  const total     = form.valor_total !== '' ? parseFloat(form.valor_total) : null;
  const abonoEfectivo =
    form.estado_pago === 'pago'   ? (total ?? 0) :
    form.estado_pago === 'abono'  ? (parseFloat(form.abono) || 0) :
    0;
  const saldo = total !== null ? Math.max(0, total - abonoEfectivo) : null;

  const pacientesFiltrados = pacientes.filter((p) =>
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    p.Paciente.includes(search),
  );

  function setField(key, val) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  function handleCategoria(cat) {
    setForm((f) => ({
      ...f,
      categoria:      cat,
      nombre_paquete: '',
      total_sesiones: '',
      valor_total:    '',
    }));
  }

  function handlePaquete(nombre) {
    const pkg = paquetes.find((p) => p.nombre === nombre);
    setForm((f) => ({
      ...f,
      nombre_paquete: nombre,
      total_sesiones: pkg ? String(pkg.sesiones) : '',
      valor_total:    pkg ? String(pkg.precio)   : f.valor_total,
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    const totalVal = parseFloat(form.valor_total);
    let abono = 0;
    let fecha_pago = null;
    if (form.estado_pago === 'pago') {
      abono = totalVal;
      fecha_pago = form.fecha_pago;
    } else if (form.estado_pago === 'abono') {
      abono = parseFloat(form.abono) || 0;
      if (abono <= 0 || abono >= totalVal) {
        setError('El abono debe ser mayor a 0 y menor al valor total.');
        return;
      }
      fecha_pago = form.fecha_pago;
    }

    let planes = [];
    if (form.categoria === 'Pilates' || form.categoria === 'Fisioterapia') {
      if (form.total_sesiones) {
        planes = [{ tipo_paquete: form.categoria, sesiones: parseInt(form.total_sesiones) }];
      }
    } else if (form.categoria === 'Combos') {
      const pkg = paquetes.find((p) => p.nombre === form.nombre_paquete);
      if (pkg?.split) {
        planes = Object.entries(pkg.split).map(([tipo_paquete, sesiones]) => ({ tipo_paquete, sesiones }));
      }
    }

    setSaving(true);
    try {
      const body = {
        paciente_id:    form.paciente_id,
        nombre_paquete: form.nombre_paquete || form.categoria,
        categoria:      form.categoria,
        total_sesiones: form.total_sesiones ? parseInt(form.total_sesiones) : null,
        valor_total:    totalVal,
        abono,
        fecha_inicio:   form.fecha_inicio,
        fecha_pago,
        metodo_pago:    form.metodo_pago,
        planes,
      };
      const nueva = await createVenta(body);
      onCreated(nueva);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar la venta.');
    } finally {
      setSaving(false);
    }
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-zinc-300';
  const labelCls = 'block text-xs font-medium text-slate-500 mb-1';

  const ESTADOS_PAGO = [
    { value: 'pago',      label: 'Pagó completo' },
    { value: 'abono',     label: 'Abonó' },
    { value: 'pendiente', label: 'Pendiente' },
  ];

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-y-auto max-h-[90vh]">
        <div className="bg-zinc-950 px-6 py-4 rounded-t-2xl flex items-center justify-between">
          <p className="text-white text-sm font-medium tracking-wide">Nueva Venta</p>
          <button onClick={onClose} className="text-zinc-400 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">

          {/* Paciente */}
          <div>
            <label className={labelCls}>Buscar paciente</label>
            <input
              type="text"
              placeholder="Nombre o cédula…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={inputCls}
            />
            {search && (
              <div className="border border-slate-200 rounded-lg mt-1 max-h-36 overflow-y-auto shadow-sm">
                {pacientesFiltrados.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-slate-400">Sin resultados</p>
                ) : (
                  pacientesFiltrados.slice(0, 8).map((p) => (
                    <button
                      key={p.Paciente}
                      type="button"
                      onClick={() => { setField('paciente_id', p.Paciente); setSearch(p.nombre); }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 transition-colors ${form.paciente_id === p.Paciente ? 'bg-zinc-50 font-semibold text-zinc-800' : 'text-slate-700'}`}
                    >
                      {p.nombre} <span className="text-slate-400 text-xs">— {p.Paciente}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Categoría */}
          <div>
            <label className={labelCls}>Categoría</label>
            <select
              value={form.categoria}
              onChange={(e) => handleCategoria(e.target.value)}
              required
              className={inputCls}
            >
              <option value="">Seleccionar…</option>
              {CATEGORIAS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {/* Paquete */}
          {form.categoria && (
            <div>
              <label className={labelCls}>Paquete</label>
              {paquetes.length > 0 ? (
                <select
                  value={form.nombre_paquete}
                  onChange={(e) => handlePaquete(e.target.value)}
                  className={inputCls}
                >
                  <option value="">Seleccionar…</option>
                  {paquetes.map((p) => (
                    <option key={p.nombre} value={p.nombre}>{p.nombre}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="Nombre del producto…"
                  value={form.nombre_paquete}
                  onChange={(e) => setField('nombre_paquete', e.target.value)}
                  className={inputCls}
                />
              )}
            </div>
          )}

          {/* Sesiones + Valor total */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Sesiones</label>
              <input
                type="number"
                min="0"
                placeholder="—"
                value={form.total_sesiones}
                onChange={(e) => setField('total_sesiones', e.target.value)}
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Valor total (COP)</label>
              <input
                type="number"
                min="1"
                required
                value={form.valor_total}
                onChange={(e) => setField('valor_total', e.target.value)}
                className={inputCls}
              />
            </div>
          </div>

          {/* Fecha de inicio del plan */}
          <div>
            <label className={labelCls}>Fecha de inicio del plan</label>
            <input
              type="date"
              required
              value={form.fecha_inicio}
              onChange={(e) => setField('fecha_inicio', e.target.value)}
              className={inputCls}
            />
            <p className="text-[11px] text-slate-400 mt-1">Desde aquí se cuentan los días de vigencia del plan.</p>
          </div>

          {/* Estado de pago */}
          <div>
            <label className={labelCls}>Pago</label>
            <div className="flex gap-2">
              {ESTADOS_PAGO.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setField('estado_pago', o.value)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all ${
                    form.estado_pago === o.value
                      ? 'bg-zinc-800 text-white border-zinc-800'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-zinc-400'
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {form.estado_pago === 'abono' && (
            <div>
              <label className={labelCls}>Abono (COP)</label>
              <input
                type="number"
                min="0"
                max={form.valor_total || undefined}
                required
                value={form.abono}
                onChange={(e) => setField('abono', e.target.value)}
                className={inputCls}
              />
            </div>
          )}

          {saldo !== null && (
            <p className={`text-xs -mt-2 font-medium ${saldo === 0 ? 'text-green-600' : 'text-amber-600'}`}>
              Saldo pendiente: {cop(saldo)}
            </p>
          )}

          {/* Método de pago + fecha de pago */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Método de pago</label>
              <select
                value={form.metodo_pago}
                onChange={(e) => setField('metodo_pago', e.target.value)}
                required
                className={inputCls}
              >
                <option value="">Seleccionar…</option>
                {METODOS_PAGO.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            {form.estado_pago !== 'pendiente' && (
              <div>
                <label className={labelCls}>Fecha de pago</label>
                <input
                  type="date"
                  required
                  value={form.fecha_pago}
                  onChange={(e) => setField('fecha_pago', e.target.value)}
                  className={inputCls}
                />
              </div>
            )}
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={saving || !form.paciente_id}
              className="flex-1 py-2.5 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? 'Guardando…' : 'Registrar venta'}
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

export default function VentasPage() {
  const [ventas,    setVentas]    = useState([]);
  const [pacientes, setPacientes] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState('');
  const [modal,     setModal]     = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    Promise.all([getVentas(), getPacientes()])
      .then(([v, p]) => { setVentas(v); setPacientes(p); })
      .catch(() => setError('Error al cargar ventas.'))
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(nueva) {
    setVentas((v) => [nueva, ...v]);
  }

  async function handleDelete(id) {
    try {
      await deleteVenta(id);
      setVentas((v) => v.filter((x) => x.id !== id));
    } catch {
      setError('Error al eliminar la venta.');
    } finally {
      setDeletingId(null);
    }
  }

  const nombresMap = Object.fromEntries(pacientes.map((p) => [p.Paciente, p.nombre]));

  const totalMes = ventas
    .filter((v) => {
      if (!v.fecha_pago) return false;
      const d = new Date();
      const [y, m] = v.fecha_pago.split('-').map(Number);
      return y === d.getFullYear() && m === d.getMonth() + 1;
    })
    .reduce((acc, v) => acc + v.abono, 0);

  const pendientes = ventas.filter((v) => v.estado === 'pendiente').length;

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Total ventas</p>
          <p className="text-3xl font-bold text-slate-800">{loading ? '…' : ventas.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Ingresos este mes</p>
          <p className="text-3xl font-bold text-slate-800">{loading ? '…' : cop(totalMes)}</p>
          <p className="text-xs text-slate-400 mt-1">abonos recibidos</p>
        </div>
        <div className={`bg-white rounded-xl border p-5 ${pendientes > 0 ? 'border-amber-200' : 'border-slate-200'}`}>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Con saldo pendiente</p>
          <p className={`text-3xl font-bold ${pendientes > 0 ? 'text-amber-600' : 'text-slate-800'}`}>
            {loading ? '…' : pendientes}
          </p>
        </div>
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Registro de ventas</h3>
          <button
            onClick={() => setModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus size={15} />
            Nueva venta
          </button>
        </div>

        {loading ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">Cargando…</div>
        ) : ventas.length === 0 ? (
          <div className="px-6 py-14 text-center text-slate-400 text-sm">
            No hay ventas registradas aún.
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-xs text-slate-400 uppercase tracking-wide">
                    <th className="px-6 py-3 text-left font-medium">Inicio</th>
                    <th className="px-6 py-3 text-left font-medium">Paciente</th>
                    <th className="px-6 py-3 text-left font-medium">Paquete</th>
                    <th className="px-6 py-3 text-left font-medium">Total</th>
                    <th className="px-6 py-3 text-left font-medium">Abono</th>
                    <th className="px-6 py-3 text-left font-medium">Saldo</th>
                    <th className="px-6 py-3 text-left font-medium">Estado</th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {ventas.map((v) => (
                    <tr key={v.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors">
                      <td className="px-6 py-3.5 text-slate-500 text-xs">{fmtDate(v.fecha_inicio)}</td>
                      <td className="px-6 py-3.5 text-slate-700 font-medium">
                        {v.paciente_nombre || nombresMap[v.paciente_id] || v.paciente_id}
                      </td>
                      <td className="px-6 py-3.5 text-slate-600 text-xs max-w-[180px] truncate">{v.nombre_paquete}</td>
                      <td className="px-6 py-3.5 text-slate-700 font-mono text-xs">{cop(v.valor_total)}</td>
                      <td className="px-6 py-3.5 text-green-700 font-mono text-xs">{cop(v.abono)}</td>
                      <td className={`px-6 py-3.5 font-mono text-xs font-semibold ${v.saldo > 0 ? 'text-amber-600' : 'text-slate-400'}`}>
                        {cop(v.saldo)}
                      </td>
                      <td className="px-6 py-3.5"><EstadoBadge estado={v.estado} /></td>
                      <td className="px-6 py-3.5 text-right">
                        {deletingId === v.id ? (
                          <div className="flex items-center justify-end gap-2">
                            <span className="text-xs text-slate-500">¿Eliminar?</span>
                            <button onClick={() => handleDelete(v.id)} className="text-xs text-red-600 font-semibold hover:underline">Sí</button>
                            <button onClick={() => setDeletingId(null)} className="text-xs text-slate-400 hover:underline">No</button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeletingId(v.id)}
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

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-slate-50">
              {ventas.map((v) => (
                <div key={v.id} className="px-4 py-4">
                  <div className="flex items-start justify-between mb-1">
                    <p className="text-sm font-semibold text-slate-800">
                      {v.paciente_nombre || nombresMap[v.paciente_id] || v.paciente_id}
                    </p>
                    <EstadoBadge estado={v.estado} />
                  </div>
                  <p className="text-xs text-slate-500 mb-2">{v.nombre_paquete} · {fmtDate(v.fecha_inicio)}</p>
                  <div className="flex gap-4 text-xs">
                    <span className="text-slate-600">Total: <strong className="font-mono">{cop(v.valor_total)}</strong></span>
                    <span className="text-green-700">Abono: <strong className="font-mono">{cop(v.abono)}</strong></span>
                    {v.saldo > 0 && <span className="text-amber-600">Saldo: <strong className="font-mono">{cop(v.saldo)}</strong></span>}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {modal && (
        <NuevaVentaModal
          pacientes={pacientes}
          onClose={() => setModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
