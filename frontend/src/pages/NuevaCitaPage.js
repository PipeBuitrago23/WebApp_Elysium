import { useEffect, useRef, useState } from 'react';
import { CheckCircle, Search } from 'lucide-react';
import { getPacientes } from '../api/pacientes';
import { createCita } from '../api/citas';

const TIPOS = ['Fisioterapia', 'Pilates', 'Sesión de cortesía'];

// Valid slots: 07:00 to 18:30 every 30 min (matches backend validation)
const VALID_SLOTS = [];
for (let h = 7; h <= 18; h++) {
  VALID_SLOTS.push(`${String(h).padStart(2, '0')}:00`);
  VALID_SLOTS.push(`${String(h).padStart(2, '0')}:30`);
}

const today = () => new Date().toISOString().split('T')[0];

const EMPTY = { paciente_id: '', fecha: today(), hora: '', tipo: '', notas: '' };

export default function NuevaCitaPage() {
  const [form, setForm] = useState({ ...EMPTY });
  const [pacientes, setPacientes] = useState([]);
  const [patientQuery, setPatientQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    getPacientes().then(setPacientes).catch(() => {});
  }, []);

  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const filtered = pacientes.filter((p) =>
    `${p.Paciente} ${p.nombre}`.toLowerCase().includes(patientQuery.toLowerCase())
  );

  function selectPaciente(p) {
    setForm((f) => ({ ...f, paciente_id: p.Paciente }));
    setPatientQuery(`${p.nombre} (${p.Paciente})`);
    setShowDropdown(false);
  }

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.paciente_id) { setError('Selecciona un paciente de la lista.'); return; }
    if (!form.tipo) { setError('Selecciona el tipo de servicio.'); return; }
    if (!form.hora) { setError('Selecciona la hora.'); return; }
    setSaving(true);
    setError('');
    try {
      const cita = await createCita({
        paciente_id: form.paciente_id,
        fecha: form.fecha,
        hora: form.hora + ':00',
        tipo: form.tipo,
        ...(form.notas ? { notas: form.notas } : {}),
      });
      setSuccess(cita);
      setForm({ ...EMPTY, fecha: form.fecha });
      setPatientQuery('');
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar la cita.');
    } finally {
      setSaving(false);
    }
  }

  if (success) {
    return (
      <div className="max-w-lg mx-auto">
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
          <CheckCircle className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-slate-800 mb-1">Cita registrada</h2>
          <p className="text-sm text-slate-500 mb-0.5 font-medium">{success.paciente_id}</p>
          <p className="text-sm text-slate-400 mb-6">
            {success.fecha} · {success.hora.slice(0, 5)} · {success.tipo}
          </p>
          <button
            onClick={() => setSuccess(null)}
            className="bg-zinc-800 hover:bg-zinc-900 text-white text-sm font-medium px-5 py-2 rounded-lg transition-all"
          >
            Registrar otra cita
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-800">Nueva cita</h2>
          <p className="text-xs text-slate-400 mt-0.5">Completa los datos para registrar la cita</p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</p>
          )}

          {/* Patient combobox */}
          <div ref={dropdownRef}>
            <label className="block text-xs font-medium text-slate-600 mb-1">Paciente</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4 pointer-events-none" />
              <input
                type="text"
                placeholder="Buscar por nombre o ID…"
                value={patientQuery}
                onChange={(e) => {
                  setPatientQuery(e.target.value);
                  setForm((f) => ({ ...f, paciente_id: '' }));
                  setShowDropdown(true);
                }}
                onFocus={() => setShowDropdown(true)}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
              />
            </div>
            {showDropdown && patientQuery.length > 0 && filtered.length > 0 && (
              <ul className="mt-1 border border-slate-200 rounded-lg bg-white shadow-md max-h-48 overflow-y-auto relative z-10">
                {filtered.slice(0, 8).map((p) => (
                  <li
                    key={p.Paciente}
                    onMouseDown={() => selectPaciente(p)}
                    className="px-4 py-2.5 text-sm cursor-pointer hover:bg-slate-50 flex justify-between items-center"
                  >
                    <span className="text-slate-800">{p.nombre}</span>
                    <span className="text-slate-400 font-mono text-xs">{p.Paciente}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Date */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Fecha</label>
            <input
              type="date"
              name="fecha"
              value={form.fecha}
              min={today()}
              onChange={handleChange}
              required
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
            />
          </div>

          {/* Tipo */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-2">Tipo de servicio</label>
            <div className="flex gap-2 flex-wrap">
              {TIPOS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, tipo: t }))}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    form.tipo === t
                      ? 'bg-zinc-800 text-white border-zinc-800'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-zinc-400'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Hora */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Hora</label>
            <select
              name="hora"
              value={form.hora}
              onChange={handleChange}
              required
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 bg-white"
            >
              <option value="">Selecciona un horario…</option>
              {VALID_SLOTS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Notas */}
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Notas <span className="text-slate-400 font-normal">(opcional)</span>
            </label>
            <textarea
              name="notas"
              value={form.notas}
              onChange={handleChange}
              rows={3}
              className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500 resize-none"
            />
          </div>

          <div className="pt-1">
            <button
              type="submit"
              disabled={saving || !form.paciente_id}
              className="w-full bg-zinc-800 hover:bg-zinc-900 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-all"
            >
              {saving ? 'Guardando…' : 'Registrar cita'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
