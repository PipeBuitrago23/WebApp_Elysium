import { createContext, useContext, useState } from 'react';
import { loginRequest, aceptarHabeasData } from '../api/auth';

const AuthContext = createContext(null);

function parseToken(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('elysium_token'));
  const [user, setUser] = useState(() => {
    const t = sessionStorage.getItem('elysium_token');
    return t ? parseToken(t) : null;
  });

  const login = async (email, password) => {
    const data = await loginRequest(email, password);
    sessionStorage.setItem('elysium_token', data.access_token);
    setToken(data.access_token);
    const decoded = parseToken(data.access_token);
    setUser(decoded);
    return decoded;
  };

  const logout = () => {
    sessionStorage.removeItem('elysium_token');
    setToken(null);
    setUser(null);
  };

  const acceptHabeas = async () => {
    await aceptarHabeasData(token);
    setUser((prev) => ({ ...prev, habeas_data_aceptado: true }));
  };

  return (
    <AuthContext.Provider value={{ token, user, login, logout, acceptHabeas, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
