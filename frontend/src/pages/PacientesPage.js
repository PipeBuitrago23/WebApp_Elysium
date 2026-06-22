import { useCallback, useEffect, useMemo, useState } from 'react';
import { CreditCard, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { getPacientes, createPaciente, updatePaciente, deletePaciente } from '../api/pacientes';
import { getPagos, createPago } from '../api/pagos';

// ── Constants ─────────────────────────────────────────────────────────────────

const TIPOS_PAQUETE = ['Pilates', 'Fisioterapia'];

const PAQUETE_STYLE = {
  Pilates:      'bg-teal-100 text-teal-700',
  Fisioterapia: 'bg-indigo-100 text-indigo-700',
};

const EMPTY_FORM = {
  Paciente: '', nombre: '', telefono: '', email: '',
  fecha_nacimiento: '', antecedentes: '', cirugias: '',
};

const EMPTY_PLAN = {
  enabled:        false,
  tipo_paquete:   'Pilates',
  total_sesiones: '',
  fecha_pago:     new Date().toISOString().split('T')[0],
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const MONTHS = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];

function fmtDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${parseInt(d)} ${MONTHS[parseInt(m) - 1]} ${y}`;
}

function addDays(isoDate, n) {
  const d = new Date(isoDate);
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
}

function venceColor(iso) {
  const today = new Date().toISOString().split('T')[0];
  const diff = Math.ceil((new Date(iso) - new Date(today)) / 86400000);
  if (diff < 0)  return 'text-red-600 font-semibold';
  if (diff <= 7) return 'text-amber-600 font-semibold';
  return 'text-green-700';
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PacientesPage() {
  const [pacientes, setPacientes] = useState([]);
  const [pagos,     setPagos]     = useState([]);
  const [search,    setSearch]    = useState('');
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState('');
  const [modal,     setModal]     = useState(null);
  const [toDelete,  setToDelete]  = useState(null);
  const [saving,    setSaving]    = useState(false);

  // Active plan per patient (most recent non-expired with sessions left)
  const pagosMap = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    const map = {};
    pagos.forEach((p) => {
      if (p.fecha_vencimiento >= today && p.sesiones_restantes > 0) {
        if (!map[p.paciente_id] || p.fecha_pago > map[p.paciente_id].fecha_pago) {
          map[p.paciente_id] = p;
        }
      }
    });
    return map;
  }, [pagos]);

  const fetchAll = useCallback(async (q) => {
    setLoading(true);
    setError('');
    try {
      const [pts, pgs] = await Promise.all([getPacientes(q), getPagos()]);
      setPacientes(pts);
      setPagos(pgs);
    } catch {
      setError('Error al cargar los datos.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => fetchAll(search), 300);
    return () => clearTimeout(t);
  }, [search, fetchAll]);

  // ── Modal openers ───────────────────────────────────────────────────────────

  function openCreate() {
    setModal({ mode: 'create', form: { ...EMPTY_FORM }, plan: { ...EMPTY_PLAN }, formError: '' });
  }

  function openEdit(p) {
    setModal({
      mode:       'edit',
      form: {
        Paciente:        p.Paciente,
        nombre:          p.nombre,
        telefono:        p.telefono        || '',
        email:           p.email           || '',
        fecha_nacimiento:p.fecha_nacimiento|| '',
        antecedentes:    p.antecedentes    || '',
        cirugias:        p.cirugias        || '',
      },
      plan:       { ...EMPTY_PLAN },
      activePlan: pagosMap[p.Paciente] || null,
      formError:  '',
    });
  }

  // ── Handlers ────────────────────────────────────────────────────────────────

  function handleFormChange(e) {
    const { name, value } = e.target;
    setModal((prev) => ({ ...prev, form: { ...prev.form, [name]: value } }));
  }

  function handlePlanChange(patch) {
    setModal((prev) => ({ ...prev, plan: { ...prev.plan, ...patch } }));
  }

  async function handleSave(e) {
    e.preventDefault();
    const { form, plan, mode } = modal;

    if (plan.enabled && (!plan.total_sesiones || parseInt(plan.total_sesiones) < 1)) {
      setModal((prev) => ({ ...prev, formError: 'Ingresa un número de sesiones válido.' }));
      return;
    }

    setSaving(true);
    setModal((prev) => ({ ...prev, formError: '' }));

    try {
      const pacienteId = form.Paciente;

      if (mode === 'create') {
        const body = { ...form };
        if (!body.fecha_nacimiento) delete body.fecha_nacimiento;
        await createPaciente(body);
      } else {
        const { Paciente: id, ...rest } = form;
        if (!rest.fecha_nacimiento) delete rest.fecha_nacimiento;
        await updatePaciente(id, rest);
      }

      if (plan.enabled) {
        await createPago({
          paciente_id:    pacienteId,
          tipo_paquete:   plan.tipo_paquete,
          total_sesiones: parseInt(plan.total_sesiones),
          fecha_pago:     plan.fecha_pago,
        });
      }

      setModal(null);
      fetchAll(search);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al guardar.';
      setModal((prev) => ({ ...prev, formError: msg }));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    try {
      await deletePaciente(toDelete);
      setToDelete(null);
      fetchAll(search);
    } catch {
      setToDelete(null);
      setError('Error al eliminar paciente.');
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Header bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Buscar por nombre, email o teléfono…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 w-72"
          />
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nuevo paciente
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              <th className="text-left px-4 py-3 font-semibold text-slate-600">ID</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Nombre</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Teléfono</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Plan</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Sesiones</th>
              <th className="text-left px-4 py-3 font-semibold text-slate-600">Vence</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={7} className="text-center py-10 text-slate-400">Cargando…</td></tr>
            )}
            {!loading && pacientes.length === 0 && (
              <tr><td colSpan={7} className="text-center py-10 text-slate-400">No se encontraron pacientes.</td></tr>
            )}
            {!loading && pacientes.map((p) => {
              const plan = pagosMap[p.Paciente];
              return (
                <tr key={p.Paciente} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.Paciente}</td>
                  <td className="px-4 py-3 font-medium text-slate-800">{p.nombre}</td>
                  <td className="px-4 py-3 text-slate-500">{p.telefono || '—'}</td>
                  <td className="px-4 py-3">
                    {plan
                      ? <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${PAQUETE_STYLE[plan.tipo_paquete] || 'bg-slate-100 text-slate-600'}`}>{plan.tipo_paquete}</span>
                      : <span className="text-xs text-slate-400">Sin plan</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-slate-700 tabular-nums">
                    {plan ? `${plan.sesiones_restantes} / ${plan.total_sesiones}` : '—'}
                  </td>
                  <td className={`px-4 py-3 text-sm ${plan ? venceColor(plan.fecha_vencimiento) : 'text-slate-400'}`}>
                    {plan ? fmtDate(plan.fecha_vencimiento) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => openEdit(p)} className="p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-teal-600 transition-colors">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => setToDelete(p.Paciente)} className="p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <h2 className="text-base font-semibold text-slate-800">
                {modal.mode === 'create' ? 'Nuevo paciente' : 'Editar paciente'}
              </h2>
              <button onClick={() => setModal(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              {modal.formError && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{modal.formError}</p>
              )}

              {/* ── Datos del paciente ── */}
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Datos del paciente</p>

              <Field label="ID paciente" name="Paciente" value={modal.form.Paciente} onChange={handleFormChange} required disabled={modal.mode === 'edit'} />
              <Field label="Nombre completo" name="nombre" value={modal.form.nombre} onChange={handleFormChange} required />
              <div className="grid grid-cols-2 gap-4">
                <Field label="Teléfono" name="telefono" value={modal.form.telefono} onChange={handleFormChange} />
                <Field label="Email" name="email" type="email" value={modal.form.email} onChange={handleFormChange} />
              </div>
              <Field label="Fecha de nacimiento" name="fecha_nacimiento" type="date" value={modal.form.fecha_nacimiento} onChange={handleFormChange} />
              <TextareaField label="Antecedentes médicos" name="antecedentes" value={modal.form.antecedentes} onChange={handleFormChange} />
              <TextareaField label="Cirugías / procedimientos" name="cirugias" value={modal.form.cirugias} onChange={handleFormChange} />

              {/* ── Plan section ── */}
              <div className="border-t border-slate-100 pt-4 space-y-3">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Plan / paquete</p>

                {/* Active plan badge (edit only) */}
                {modal.mode === 'edit' && modal.activePlan && (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 flex flex-wrap items-center gap-3">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${PAQUETE_STYLE[modal.activePlan.tipo_paquete] || ''}`}>
                      {modal.activePlan.tipo_paquete}
                    </span>
                    <span className="text-sm text-slate-700">
                      {modal.activePlan.sesiones_restantes} / {modal.activePlan.total_sesiones} sesiones
                    </span>
                    <span className={`text-sm ${venceColor(modal.activePlan.fecha_vencimiento)}`}>
                      Vence {fmtDate(modal.activePlan.fecha_vencimiento)}
                    </span>
                  </div>
                )}

                {modal.mode === 'edit' && !modal.activePlan && (
                  <p className="text-sm text-slate-400">Este paciente no tiene un plan activo.</p>
                )}

                {/* Toggle */}
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={modal.plan.enabled}
                    onClick={() => handlePlanChange({ enabled: !modal.plan.enabled })}
                    className={`relative w-10 h-5 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-1 ${modal.plan.enabled ? 'bg-teal-600' : 'bg-slate-200'}`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${modal.plan.enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                  </button>
                  <span className="text-sm font-medium text-slate-700 flex items-center gap-1.5">
                    <CreditCard className="w-4 h-4 text-slate-400" />
                    {modal.mode === 'create' ? 'Asignar plan ahora' : 'Agregar nuevo plan'}
                  </span>
                </label>

                {/* Plan fields */}
                {modal.plan.enabled && (
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
                    {/* Tipo */}
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-2">Tipo de paquete</label>
                      <div className="flex gap-2">
                        {TIPOS_PAQUETE.map((t) => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => handlePlanChange({ tipo_paquete: t })}
                            className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-colors ${
                              modal.plan.tipo_paquete === t
                                ? t === 'Pilates'
                                  ? 'bg-teal-600 text-white border-teal-600'
                                  : 'bg-indigo-600 text-white border-indigo-600'
                                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                            }`}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Sesiones + fecha pago */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">Sesiones totales</label>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          value={modal.plan.total_sesiones}
                          onChange={(e) => handlePlanChange({ total_sesiones: e.target.value })}
                          placeholder="Ej. 10"
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-slate-600 mb-1">Fecha de pago</label>
                        <input
                          type="date"
                          value={modal.plan.fecha_pago}
                          onChange={(e) => handlePlanChange({ fecha_pago: e.target.value })}
                          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white"
                        />
                      </div>
                    </div>

                    {/* Expiration preview */}
                    {modal.plan.fecha_pago && (
                      <div className="flex items-center gap-2 text-sm bg-teal-50 border border-teal-100 rounded-lg px-3 py-2">
                        <span className="text-teal-600 font-medium">Vigencia:</span>
                        <span className="text-teal-800 font-semibold">
                          {fmtDate(modal.plan.fecha_pago)} → {fmtDate(addDays(modal.plan.fecha_pago, 45))}
                        </span>
                        <span className="text-teal-500 text-xs ml-auto">45 días</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setModal(null)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {toDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-base font-semibold text-slate-800 mb-2">Eliminar paciente</h2>
            <p className="text-sm text-slate-600 mb-6">
              ¿Seguro que deseas eliminar a <span className="font-medium">{toDelete}</span>?
              Esta acción no se puede deshacer.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setToDelete(null)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">Cancelar</button>
              <button onClick={handleDelete} className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors">
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Field helpers ─────────────────────────────────────────────────────────────

function Field({ label, name, value, onChange, required, disabled, type = 'text' }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        required={required}
        disabled={disabled}
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:bg-slate-50 disabled:text-slate-400"
      />
    </div>
  );
}

function TextareaField({ label, name, value, onChange }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <textarea
        name={name}
        value={value}
        onChange={onChange}
        rows={3}
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none"
      />
    </div>
  );
}
