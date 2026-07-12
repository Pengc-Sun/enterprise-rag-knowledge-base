import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { login, register } from '../api/auth';
import { clearStoredToken, getStoredToken, storeToken } from '../api/client';
import type { RegisterPayload } from '../api/types';

type Credentials = {
  email: string;
  password: string;
};

type AuthContextValue = {
  token: string | null;
  isAuthenticated: boolean;
  signIn: (credentials: Credentials) => Promise<void>;
  signUp: (payload: RegisterPayload) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  const persistToken = useCallback((nextToken: string) => {
    storeToken(nextToken);
    setToken(nextToken);
  }, []);

  const signIn = useCallback(
    async (credentials: Credentials) => {
      const response = await login(credentials);
      persistToken(response.access_token);
    },
    [persistToken],
  );

  const signUp = useCallback(
    async (payload: RegisterPayload) => {
      await register(payload);
      const response = await login({ email: payload.email, password: payload.password });
      persistToken(response.access_token);
    },
    [persistToken],
  );

  const signOut = useCallback(() => {
    clearStoredToken();
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      signIn,
      signUp,
      signOut,
    }),
    [signIn, signOut, signUp, token],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}
