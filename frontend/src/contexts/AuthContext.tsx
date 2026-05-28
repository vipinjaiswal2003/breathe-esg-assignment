import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User, Tenant } from '../types';
import { authApi, tenantApi } from '../api/client';

interface AuthContextType {
  user: User | null;
  tenants: Tenant[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  switchTenant: (tenantId: number) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authApi.me();
      setUser(userData);
    } catch {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      setUser(null);
    }
  }, []);

  const loadTenants = useCallback(async () => {
    try {
      const data = await tenantApi.list();
      setTenants(data);
    } catch {
      setTenants([]);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      Promise.all([refreshUser(), loadTenants()]).finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [refreshUser, loadTenants]);

  const login = async (username: string, password: string) => {
    const res = await authApi.login({ username, password });
    localStorage.setItem('auth_token', res.token);
    localStorage.setItem('auth_user', JSON.stringify(res.user));
    setUser(res.user);
    await loadTenants();
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    setUser(null);
    setTenants([]);
    window.location.href = '/login';
  };

  const switchTenant = async (tenantId: number) => {
    await tenantApi.setActive(tenantId);
    await refreshUser();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenants,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        switchTenant,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
