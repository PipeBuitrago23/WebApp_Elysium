import { Navigate } from 'react-router-dom';
import { useTenant } from '../context/TenantContext';

// Same pattern as PrivateRoute/MedicoRoute, gated on plan features instead
// of auth. Waits for the tenant config to load before deciding, so a page
// refresh doesn't flash-redirect someone who does have the feature.
export default function FeatureRoute({ feature, children }) {
  const { hasFeature, loading } = useTenant();
  if (loading) return null;
  if (!hasFeature(feature)) return <Navigate to="/dashboard" replace />;
  return children;
}
