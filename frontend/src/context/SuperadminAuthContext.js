import { createContext, useContext, useState } from 'react';
import { superadminLogin } from '../api/superadmin';

// Contexto de auth SEPARADO del AuthContext de los tenants — no comparten token
// ni estado. Key propia en sessionStorage (elysium_superadmin_token).
const SuperadminAuthContext = createContext(null);
const TOKEN_KEY = 'elysium_superadmin_token';

export function SuperadminAuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY));

  const login = async (email, password) => {
    const data = await superadminLogin(email, password);
    sessionStorage.setItem(TOKEN_KEY, data.access_token);
    setToken(data.access_token);
  };

  const logout = () => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
  };

  return (
    <SuperadminAuthContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
      {children}
    </SuperadminAuthContext.Provider>
  );
}

export const useSuperadminAuth = () => useContext(SuperadminAuthContext);
