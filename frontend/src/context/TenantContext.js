import { createContext, useContext, useEffect, useState } from 'react';
import { getTenantConfig } from '../api/tenant';

const TenantContext = createContext(null);

// Fallback when /tenant/config hasn't resolved yet (or failed) — matches the
// current zinc palette / "Tu Estudio" copy so pages render sensibly before
// the real branding loads, instead of showing nothing.
const FALLBACK_TENANT = { nombre_comercial: 'Tu Estudio', branding: {} };

export function TenantProvider({ children }) {
  const [tenant, setTenant] = useState(FALLBACK_TENANT);
  const [features, setFeatures] = useState(new Set());
  const [servicios, setServicios] = useState([]);
  const [horario, setHorario] = useState(null);
  const [sesionCortesia, setSesionCortesia] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTenantConfig()
      .then((data) => {
        setTenant({ nombre_comercial: data.nombre_comercial, branding: data.branding || {} });
        setFeatures(new Set(data.features || []));
        setServicios(data.servicios || []);
        setHorario(data.horario || null);
        setSesionCortesia(data.sesion_cortesia || null);
      })
      .catch(() => {
        // Leave the fallback tenant/empty features/servicios in place — the
        // page that made this request already got its own 404/error to
        // handle (the same tenant-resolution failure hits every endpoint).
      })
      .finally(() => setLoading(false));
  }, []);

  const hasFeature = (nombre) => features.has(nombre);

  // Booking "tipo" options: real servicios, plus the "Sesión de cortesía"
  // pseudo-type when this tenant has it enabled — same rule the backend
  // applies in core/servicios.py:tipos_validos().
  const tiposCita = [
    ...servicios.map((s) => s.nombre),
    ...(sesionCortesia?.habilitada ? ['Sesión de cortesía'] : []),
  ];

  return (
    <TenantContext.Provider
      value={{ tenant, features, servicios, horario, sesionCortesia, tiposCita, loading, hasFeature }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export const useTenant = () => useContext(TenantContext);
