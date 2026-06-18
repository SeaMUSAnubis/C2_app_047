import { Navigate, Outlet } from 'react-router-dom';
import { APP_ROUTES } from '../../lib/constants';
import { isAuthenticated } from '../../lib/authStore';

export function ProtectedRoute() {
  if (!isAuthenticated()) {
    return <Navigate to={APP_ROUTES.login} replace />;
  }

  return <Outlet />;
}
