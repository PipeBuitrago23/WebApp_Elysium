import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { SuperadminAuthProvider, useSuperadminAuth } from './context/SuperadminAuthContext';
import SuperadminLoginPage from './pages/SuperadminLoginPage';
import SuperadminTenantsPage from './pages/SuperadminTenantsPage';
import SuperadminTenantDetailPage from './pages/SuperadminTenantDetailPage';

// Árbol del panel superadmin — completamente separado del árbol de los tenants
// (no está envuelto en TenantProvider/AuthProvider). App.js decide cuál montar
// según el path (/superadmin/*). Su propio contexto de auth y su propio token.
function Guard({ children }) {
  const { isAuthenticated } = useSuperadminAuth();
  return isAuthenticated ? children : <Navigate to="/superadmin/login" replace />;
}

export default function SuperadminApp() {
  return (
    <SuperadminAuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/superadmin/login" element={<SuperadminLoginPage />} />
          <Route path="/superadmin" element={<Guard><SuperadminTenantsPage /></Guard>} />
          <Route path="/superadmin/tenants/:slug" element={<Guard><SuperadminTenantDetailPage /></Guard>} />
          <Route path="*" element={<Navigate to="/superadmin" replace />} />
        </Routes>
      </BrowserRouter>
    </SuperadminAuthProvider>
  );
}
