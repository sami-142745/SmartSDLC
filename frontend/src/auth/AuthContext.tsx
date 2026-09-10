import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { clearToken, getToken, setToken } from '../api/client';
import { userFromToken, validateToken } from '../api/auth';
import type { UserSummary } from '../types';

interface AuthState {
  user: UserSummary | null;
  token: string | null;
  initialized: boolean;
}

export interface AuthContextValue extends AuthState {
  setSession: (token: string, user: UserSummary) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const UNAUTHENTICATED: AuthState = { user: null, token: null, initialized: true };

interface AuthProviderProps {
  children: ReactNode;
  /** Test hook: seed a session and skip the async restore. */
  initialToken?: string;
  initialUser?: UserSummary;
}

export function AuthProvider({
  children,
  initialToken,
  initialUser,
}: AuthProviderProps) {
  const [state, setState] = useState<AuthState>(() => {
    if (initialToken) {
      return { token: initialToken, user: initialUser ?? userFromToken(initialToken), initialized: true };
    }
    const token = getToken();
    if (!token) return UNAUTHENTICATED;
    return { token, user: userFromToken(token), initialized: false };
  });

  useEffect(() => {
    if (initialToken !== undefined) return;

    const token = getToken();
    if (!token) return;

    let cancelled = false;
    validateToken()
      .then((valid) => {
        if (cancelled) return;
        if (!valid) {
          clearToken();
          setState(UNAUTHENTICATED);
          return;
        }
        setState((prev) => ({ ...prev, initialized: true }));
      })
      .catch(() => {
        if (cancelled) return;
        setState((prev) => ({ ...prev, initialized: true }));
      });
    return () => {
      cancelled = true;
    };
  }, [initialToken]);

  const setSession = useCallback((token: string, user: UserSummary) => {
    setToken(token);
    setState({ token, user, initialized: true });
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setState(UNAUTHENTICATED);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, setSession, logout }),
    [state, setSession, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}