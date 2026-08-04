import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useContext, useEffect, useState } from "react";

import * as authApi from "../api/auth";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { reportDeviceTimezone } from "../api/profile";

/** "Manter conectado" — a escolha da pessoa na tela de entrada.
 *
 * O token sempre foi gravado e sempre sobreviveu ao fechamento do app, sem
 * ninguém perguntar. Isso é o certo pra quase todo mundo (e continua sendo o
 * padrão), mas não pra quem entrou no aparelho de outra pessoa: pra essa pessoa
 * a sessão tem que morrer quando o app fecha.
 *
 * Guardado FORA do token, como bandeira própria: no boot, um token sem a
 * bandeira ligada é descartado antes de ser usado. */
const KEEP_SIGNED_IN_KEY = "appfit.auth.keepSignedIn";

type AuthContextValue = {
  isLoading: boolean;
  user: authApi.UserRead | null;
  signIn: (email: string, password: string, keepSignedIn?: boolean) => Promise<void>;
  signUp: (payload: {
    email: string;
    password: string;
    handle: string;
    display_name: string;
    keepSignedIn?: boolean;
  }) => Promise<void>;
  /** Entrar com Google. `handle`/`displayName` só são exigidos no PRIMEIRO
   * acesso com essa conta Google (o backend cria o usuário na hora); num login
   * seguinte eles são ignorados. */
  signInWithGoogle: (
    idToken: string,
    extra?: { handle?: string; displayName?: string },
    keepSignedIn?: boolean
  ) => Promise<void>;
  /** Usa um access_token que a pessoa já tem em mãos (ex.: o reset de senha
   * devolve um, pra ela entrar direto sem digitar a senha nova de novo). */
  signInWithToken: (accessToken: string, keepSignedIn?: boolean) => Promise<void>;
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
    // Quem desmarcou "manter conectado" não volta logado: o token existe (foi
    // gravado no login), mas a bandeira diz que ele não valia pra além daquela
    // sessão. Descartar aqui, ANTES de usar, é o que faz a escolha valer mesmo
    // se o app tiver sido fechado à força.
    if ((await AsyncStorage.getItem(KEEP_SIGNED_IN_KEY)) === "false") {
      await AsyncStorage.multiRemove([TOKEN_STORAGE_KEY, KEEP_SIGNED_IN_KEY]);
      setIsLoading(false);
      return;
    }
    try {
      const currentUser = await authApi.fetchCurrentUser();
      setUser(currentUser);
      reportDeviceTimezone();
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

  async function persistTokenAndLoadUser(accessToken: string, keepSignedIn: boolean) {
    // O token é gravado nos dois casos — é dele que as chamadas desta sessão
    // dependem. O que a bandeira decide é se ele SOBREVIVE ao fechamento do app
    // (ver loadFromStoredToken).
    await AsyncStorage.multiSet([
      [TOKEN_STORAGE_KEY, accessToken],
      [KEEP_SIGNED_IN_KEY, keepSignedIn ? "true" : "false"],
    ]);
    const currentUser = await authApi.fetchCurrentUser();
    setUser(currentUser);
    // Não dá await: o app não espera infra pra abrir.
    reportDeviceTimezone();
  }

  async function signIn(email: string, password: string, keepSignedIn = true) {
    const { access_token } = await authApi.login({ email, password });
    await persistTokenAndLoadUser(access_token, keepSignedIn);
  }

  async function signUp(payload: {
    email: string;
    password: string;
    handle: string;
    display_name: string;
    keepSignedIn?: boolean;
  }) {
    const { keepSignedIn = true, ...credenciais } = payload;
    const { access_token } = await authApi.register(credenciais);
    await persistTokenAndLoadUser(access_token, keepSignedIn);
  }

  async function signInWithGoogle(
    idToken: string,
    extra?: { handle?: string; displayName?: string },
    keepSignedIn = true
  ) {
    const { access_token } = await authApi.loginWithGoogle({
      id_token: idToken,
      handle: extra?.handle,
      display_name: extra?.displayName,
    });
    await persistTokenAndLoadUser(access_token, keepSignedIn);
  }

  async function signInWithToken(accessToken: string, keepSignedIn = true) {
    await persistTokenAndLoadUser(accessToken, keepSignedIn);
  }

  async function signOut() {
    await AsyncStorage.multiRemove([TOKEN_STORAGE_KEY, KEEP_SIGNED_IN_KEY]);
    setUser(null);
  }

  async function refreshUser() {
    const currentUser = await authApi.fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  return (
    <AuthContext.Provider
      value={{ isLoading, user, signIn, signUp, signInWithGoogle, signInWithToken, signOut, refreshUser }}
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
