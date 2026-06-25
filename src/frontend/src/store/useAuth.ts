import { useContext } from 'react';
import { AuthContext } from './authContext';

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth phải được dùng bên trong AuthProvider');
  }
  return context;
}
