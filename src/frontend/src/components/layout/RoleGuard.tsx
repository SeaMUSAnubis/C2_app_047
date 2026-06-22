import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../store/useAuth';
import type { UserRole } from '../../types';

export default function RoleGuard({ allowedRoles }: { allowedRoles: UserRole[] }) {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
