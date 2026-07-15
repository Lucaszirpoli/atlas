import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

// Em dev, o Expo Go acessa a máquina host pelo IP local, não localhost.
// Ajuste EXPO_PUBLIC_API_URL no .env do mobile para o IP da sua máquina.
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export const API_BASE_URL = API_URL;

/** Resolve uma URL de mídia (foto/gif de exercício) vinda do backend. Imagens
 * externas (base aberta no GitHub) já vêm absolutas (http...) e são usadas como
 * estão; imagens hospedadas pelo nosso backend vêm relativas ("/static/...") e
 * recebem o endereço do backend na frente — assim funcionam em qualquer host
 * (dev local, Railway, etc.) sem endereço fixo gravado no banco. */
export function resolveMediaUrl(url?: string | null): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${API_BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}

export const TOKEN_STORAGE_KEY = "@appfit/access_token";

// timeout: sem isso, uma conexão que trava (rede fora do ar, bloqueio do
// sistema, etc.) fica esperando pra sempre — o app parece "não fazer nada"
// em vez de mostrar um erro.
export const api = axios.create({ baseURL: API_URL, timeout: 15000 });

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
