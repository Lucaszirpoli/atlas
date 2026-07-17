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
//
// 15s era CURTO DEMAIS e causava o pior tipo de bug: o app dizia "não foi
// possível adicionar" e o alimento/treino aparecia salvo assim que a pessoa
// voltava. O motivo é que o timeout do axios aborta só do lado do CELULAR — o
// servidor não fica sabendo e termina de salvar. Com o backend do Railway
// dormindo por inatividade, a primeira chamada leva mais de 15s pra acordar, e
// toda escrita nesse intervalo virava um erro mentiroso.
//
// O custo do erro é assimétrico: esperar alguns segundos a mais incomoda;
// dizer que falhou o que deu certo destrói a confiança na contagem inteira.
export const REQUEST_TIMEOUT_MS = 30000;

// Escrita (registrar refeição, salvar treino, check-in) tem prazo maior: aqui
// desistir cedo não cancela nada no servidor, só mente pro usuário.
export const WRITE_TIMEOUT_MS = 60000;

export const api = axios.create({ baseURL: API_URL, timeout: REQUEST_TIMEOUT_MS });

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Prazo maior pra toda ESCRITA, aqui e não em cada chamada: são 30+ pontos
  // de POST/DELETE espalhados, e passar o timeout um a um garante esquecer o
  // próximo que alguém escrever — justamente o que produziu o "não foi possível
  // adicionar" que adicionava. Só mexe em quem está no padrão: se a chamada
  // pediu um prazo próprio (a IA usa 90s), respeita.
  const metodo = (config.method ?? "get").toLowerCase();
  const ehEscrita = metodo === "post" || metodo === "put" || metodo === "patch" || metodo === "delete";
  if (ehEscrita && config.timeout === REQUEST_TIMEOUT_MS) {
    config.timeout = WRITE_TIMEOUT_MS;
  }
  return config;
});

// Timeout numa ESCRITA não significa "não salvou": o axios aborta só no
// celular, e o servidor termina o trabalho sem saber que alguém desistiu. As
// telas leem err.response.data.detail e, num timeout, response nem existe —
// caíam no genérico "Tente novamente", que soa como "não foi". Aqui a mensagem
// passa a dizer a verdade: pode ter dado certo, confira antes de refazer. Isso
// evita o pior desfecho, que é a pessoa registrar a refeição duas vezes.
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const metodo = (error?.config?.method ?? "get").toLowerCase();
    const ehEscrita = ["post", "put", "patch", "delete"].includes(metodo);
    const ehTimeout = error?.code === "ECONNABORTED" || /timeout/i.test(error?.message ?? "");
    if (ehEscrita && ehTimeout && !error.response) {
      error.response = {
        data: {
          detail:
            "A conexão demorou demais e não deu pra confirmar. Isso NÃO quer dizer que " +
            "falhou — pode ter sido salvo. Confira antes de fazer de novo, pra não duplicar.",
        },
      };
    }
    return Promise.reject(error);
  }
);
