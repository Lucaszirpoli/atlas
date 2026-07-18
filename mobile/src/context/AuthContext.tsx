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
  refreshUser: () => Promise<authApi.UserRead | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<authApi.UserRead | null>(null);

  async function loadFromStoredToken() {
    const token = await AsyncStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) {
      // Login automático SÓ em desenvolvimento (__DEV__ some sozinho em
      // builds de produção — nunca vai pra loja assim). Poupa relogar toda
      // hora enquanto o app ainda não foi lançado. Se falhar (backend fora
      // do ar, usuário de dev não existe), cai normalmente na tela de login.
      if (__DEV__) {
        try {
          const { access_token } = await authApi.login({
            email: "lucas@appfit.com",
            password: "senha12345",
          });
          await AsyncStorage.setItem(TOKEN_STORAGE_KEY, access_token);
          const currentUser = await authApi.fetchCurrentUser();
          setUser(currentUser);
          setIsLoading(false);
          return;
        } catch {
          // segue pro fluxo normal (tela de login)
        }
      }
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

  // O boot/login NÃO chama mais o RevenueCat. Antes, configurePurchases()
  // rodava aqui pra TODO login — inclusive de conta recém-criada, no
  // primeiríssimo instante de uso. Um amigo do usuário via tela branca bem
  // nessa janela; o try/catch (v20) não resolveu porque um crash NATIVO em
  // thread de segundo plano do SDK (ex: inicializando o Billing Library do
  // Google pela primeira vez naquele aparelho/conta) não é interceptável por
  // try/catch do JS — a ponte já morreu antes de qualquer exceção chegar ao
  // React. Mover pra ProfileScreen/PaywallScreen (only-when-needed) tira o
  // RevenueCat inteiro do caminho crítico do primeiro login — quem nunca abre
  // a tela de assinatura nunca toca nesse SDK. Ver purchases.ts e
  // ProfileScreen/PaywallScreen para onde isso agora roda.

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
    return currentUser;
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
