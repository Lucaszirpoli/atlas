import { api } from "./client";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type UserRead = {
  id: number;
  email: string;
  handle: string;
  display_name: string;
  plan: "free" | "pro";
  onboarding_completed: boolean;
  ai_free_credits: number;
  created_at: string;
};

export async function register(payload: {
  email: string;
  password: string;
  handle: string;
  display_name: string;
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/register", payload);
  return data;
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/login", payload);
  return data;
}

export async function loginWithGoogle(payload: {
  id_token: string;
  handle?: string;
  display_name?: string;
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/google", payload);
  return data;
}

export async function loginWithApple(payload: {
  id_token: string;
  handle?: string;
  display_name?: string;
}): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/apple", payload);
  return data;
}

export async function fetchCurrentUser(): Promise<UserRead> {
  const { data } = await api.get<UserRead>("/users/me");
  return data;
}

export async function checkHandleAvailability(
  handle: string
): Promise<{ handle: string; available: boolean }> {
  const { data } = await api.get(`/users/handle-availability/${handle}`);
  return data;
}
