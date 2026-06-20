import { Navigate } from 'react-router-dom';
import { useAuth } from '../../store/authStore';
import React from 'react';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
