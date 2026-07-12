import { useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import LoginPage from './pages/LoginPage';
import DashboardLayout from './layouts/DashboardLayout';
import DashboardHome from './pages/DashboardHome';
import PacientesPage from './pages/PacientesPage';
import NuevaCitaPage from './pages/NuevaCitaPage';
import AgendaPage from './pages/AgendaPage';
import PortalPage from './pages/PortalPage';


// ── Privacy policy content (shared between both modal layers) ─────────────────

function PolicyContent() {
  return (
    <div className="space-y-4 text-slate-600 text-sm leading-relaxed">
      <p className="font-bold text-slate-800 text-base">
        Política de Privacidad y Tratamiento de Datos Personales
      </p>
      <p>
        <span className="font-semibold text-slate-700">Responsable del Tratamiento:</span>{' '}
        Elysium Fisio-Pilates, identificado con el NIT registrado en Cámara de Comercio,
        con domicilio en Colombia.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Finalidad del Tratamiento:</span>{' '}
        Los datos personales y datos sensibles de salud recopilados serán tratados
        exclusivamente para: (i) la gestión y agendamiento de citas terapéuticas;
        (ii) el seguimiento de la evolución y bienestar del paciente;
        (iii) el envío de recordatorios y comunicaciones relacionadas con el servicio;
        y (iv) el cumplimiento de obligaciones legales en materia de salud.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Datos Sensibles:</span>{' '}
        Conforme a la Ley 1581 de 2012 y el Decreto 1377 de 2013, los datos de
        salud —incluyendo historial clínico, antecedentes médicos, diagnósticos y
        evolución terapéutica— son clasificados como <em>datos sensibles</em> y
        gozan de especial protección. Su tratamiento requiere autorización expresa,
        libre, previa e informada del titular.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Derechos del Titular:</span>{' '}
        Como titular de sus datos, usted tiene derecho a: conocer, actualizar,
        rectificar y suprimir la información contenida en nuestras bases de datos;
        ser informado sobre el uso que se da a sus datos; presentar quejas ante la
        Superintendencia de Industria y Comercio (SIC); y revocar la autorización
        en cualquier momento, siempre que no exista impedimento legal o contractual.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Conservación:</span>{' '}
        La información será conservada durante el tiempo que dure la relación
        terapéutica y los plazos legales de conservación de historias clínicas
        según la Resolución 1995 de 1999 del Ministerio de Salud de Colombia
        (mínimo 15 años).
      </p>
      <p>
        <span className="font-semibold text-slate-700">Transferencia de Datos:</span>{' '}
        Elysium Fisio-Pilates no compartirá, venderá ni cederá sus datos personales
        a terceros sin su consentimiento previo, salvo obligación legal.
      </p>
      <p>
        <span className="font-semibold text-slate-700">Contacto:</span>{' '}
        Para ejercer sus derechos o consultar la política completa, comuníquese con
        nosotros a través de los canales de atención de Elysium Fisio-Pilates.
        Este documento puede actualizarse periódicamente; los cambios serán
        comunicados a los titulares con la debida anticipación.
      </p>
    </div>
  );
}


// ── Habeas Data modal (Escenario B — usuarios ya registrados) ─────────────────

function HabeasDataModal() {
  const { user, acceptHabeas } = useAuth();
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [policyOpen, setPolicyOpen] = useState(false);

  if (!user || user.habeas_data_aceptado !== false) return null;

  async function handleAccept() {
    setLoading(true);
    setError('');
    try {
      await acceptHabeas();
    } catch {
      setError('No pudimos registrar tu autorización. Por favor intenta de nuevo.');
      setLoading(false);
    }
  }

  return (
    <>
      {/* ── Main consent modal ── */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">

          {/* Header */}
          <div className="bg-zinc-950 px-6 py-5 text-center">
            <p className="text-[10px] text-zinc-400 uppercase tracking-[0.3em] mb-1.5">
              Protección de Datos Personales
            </p>
            <h2 className="text-white text-sm font-light tracking-[0.25em] uppercase">
              Elysium Fisio-Pilates
            </h2>
          </div>

          {/* Body */}
          <div className="px-6 pt-6 pb-7">
            <h3 className="text-slate-800 font-bold text-lg mb-3 leading-snug">
              Autorización de Tratamiento de Datos Personales
            </h3>
            <p className="text-slate-500 text-sm leading-relaxed mb-4">
              Para continuar garantizando un servicio de la más alta calidad y
              seguridad médica, requerimos su autorización expresa conforme a la{' '}
              <span className="font-semibold text-slate-700">Ley 1581 de 2012</span>{' '}
              (Habeas Data) y el Decreto 1377 de 2013.
            </p>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-5">
              <p className="text-slate-600 text-sm leading-relaxed">
                Elysium Fisio-Pilates solicita su consentimiento para tratar sus{' '}
                <span className="font-semibold text-slate-800">
                  datos personales y datos sensibles de salud
                </span>{' '}
                —incluyendo historial clínico, antecedentes y evolución terapéutica—
                con la finalidad exclusiva de gestionar su atención, agendar citas
                y hacer seguimiento a su proceso de bienestar.
              </p>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-red-700 text-sm mb-4">
                {error}
              </div>
            )}

            <button
              onClick={handleAccept}
              disabled={loading}
              className="w-full py-3.5 bg-zinc-800 hover:bg-zinc-900 active:bg-zinc-950 text-white font-semibold rounded-xl transition-all disabled:opacity-50 text-sm tracking-wide mb-3"
            >
              {loading ? 'Registrando autorización…' : 'Acepto y deseo continuar'}
            </button>

            <div className="text-center">
              <button
                onClick={() => setPolicyOpen(true)}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors underline underline-offset-2"
              >
                Leer Política de Privacidad completa
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Policy detail sub-modal ── */}
      {policyOpen && (
        <div className="fixed inset-0 bg-black/70 z-[110] flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[85vh]">
            <div className="bg-zinc-950 px-6 py-4 rounded-t-2xl flex items-center justify-between shrink-0">
              <p className="text-white text-xs font-light tracking-widest uppercase">
                Política de Privacidad
              </p>
              <button
                onClick={() => setPolicyOpen(false)}
                className="text-zinc-400 hover:text-white text-2xl leading-none transition-colors"
                aria-label="Cerrar"
              >
                ×
              </button>
            </div>
            <div className="overflow-y-auto px-6 py-5 flex-1">
              <PolicyContent />
            </div>
            <div className="px-6 pb-5 pt-3 shrink-0 border-t border-slate-100">
              <button
                onClick={() => setPolicyOpen(false)}
                className="w-full py-3 bg-zinc-800 hover:bg-zinc-900 text-white font-semibold rounded-xl text-sm transition-all"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}


// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/portal" element={<PortalPage />} />
          <Route
            path="/"
            element={<PrivateRoute><DashboardLayout /></PrivateRoute>}
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"  element={<DashboardHome />} />
            <Route path="agenda"     element={<AgendaPage />} />
            <Route path="pacientes"  element={<PacientesPage />} />
            <Route path="nueva-cita" element={<NuevaCitaPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
      <HabeasDataModal />
    </AuthProvider>
  );
}

export default App;
