import { useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser } from '../types';
import { clearAuthSession, getAuthUser, saveAuthSession } from '../lib/authStore';
import { AuthContext } from './authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    return getAuthUser();
  });

  const login = (newUser: AuthUser, token: string) => {
    saveAuthSession({ accessToken: token, user: newUser });
    setUser(newUser);
  };

  const logout = () => {
    clearAuthSession();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
