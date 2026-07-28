import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function MedicoRoute({ children }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.es_medico) return <Navigate to="/login" replace />;
  return children;
}
