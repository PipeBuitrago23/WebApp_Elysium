import axios from 'axios';
import { apiUrl } from '../config/runtime';

// Axios instance SEPARADO del client de los tenants (api/client.js): su propio
// token (elysium_superadmin_token) y SIN header X-Tenant-Slug — las rutas de
// superadmin operan a través de todos los tenants y están exentas de la
// resolución de tenant en el backend. Mismo baseURL (el mismo backend).
const superadminClient = axios.create({ baseURL: apiUrl });

superadminClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('elysium_superadmin_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Un 401 en cualquier ruta que no sea el login (token vencido / operador
// suspendido) limpia la sesión y manda al login. En el login mismo, el 401 es
// "credenciales incorrectas" y lo maneja la pantalla.
superadminClient.interceptors.response.use(
  (r) => r,
  (error) => {
    const url = error.config?.url || '';
    if (error.response?.status === 401 && !url.includes('/superadmin/auth/login')) {
      sessionStorage.removeItem('elysium_superadmin_token');
      if (!window.location.pathname.endsWith('/superadmin/login')) {
        window.location.href = '/superadmin/login';
      }
    }
    return Promise.reject(error);
  },
);

export default superadminClient;
