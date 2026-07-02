import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useContext, useEffect, useState } from "react";

import * as authApi from "../api/auth";
import { TOKEN_STORAGE_KEY } from "../api/client";

type AuthContextValue = {
  isLoading: boolean;
  user: authApi.UserRead | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (payload: {
    email: string;
    password: string;
    handle: string;
    display_name: string;
  }) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<authApi.UserRead | null>(null);

  async function loadFromStoredToken() {
    const token = await AsyncStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const currentUser = await authApi.fetchCurrentUser();
      setUser(currentUser);
    } catch {
      await AsyncStorage.removeItem(TOKEN_STORAGE_KEY);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadFromStoredToken();
  }, []);

  async function persistTokenAndLoadUser(accessToken: string) {
    await AsyncStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
    const currentUser = await authApi.fetchCurrentUser();
    setUser(currentUser);
  }

  async function signIn(email: string, password: string) {
    const { access_token } = await authApi.login({ email, password });
    await persistTokenAndLoadUser(access_token);
  }

  async function signUp(payload: {
    email: string;
    password: string;
    handle: string;
    display_name: string;
  }) {
    const { access_token } = await authApi.register(payload);
    await persistTokenAndLoadUser(access_token);
  }

  async function signOut() {
    await AsyncStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
  }

  async function refreshUser() {
    const currentUser = await authApi.fetchCurrentUser();
    setUser(currentUser);
  }

  return (
    <AuthContext.Provider
      value={{ isLoading, user, signIn, signUp, signOut, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth precisa estar dentro de um AuthProvider");
  }
  return ctx;
}
