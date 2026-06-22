export type UserRole = 'admin' | 'security_manager' | 'analyst' | 'employee';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

export interface LoginResponse {
  accessToken: string;
  user: AuthUser;
}
