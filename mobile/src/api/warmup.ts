import { AppState, type AppStateStatus } from "react-native";

import { api } from "./client";

/** ACORDA O BACKEND ANTES DA PESSOA PRECISAR DELE.
 *
 * O servidor no Railway hiberna por inatividade e leva alguns segundos pra
 * voltar. Quem sofria com isso era sempre o primeiro toque: a pessoa abria o
 * app, tocava um botão e ficava olhando o spinner enquanto o servidor
 * levantava — parecia lentidão do app, não do servidor dormindo.
 *
 * `client.ts` já cobre a FALHA desse instante (retenta uma vez, e nunca mente
 * dizendo que a escrita falhou). O que faltava era não chegar nesse instante:
 * um GET barato em /health assim que o app abre, e de novo toda vez que ele
 * volta do segundo plano, dá ao servidor o tempo de acordar ENQUANTO a pessoa
 * ainda está navegando até o que quer fazer.
 *
 * Deliberadamente silencioso e sem await: se falhar, não muda nada — o
 * caminho normal continua valendo. Isto é otimização de latência, não uma
 * dependência.
 */

/** Espaço mínimo entre dois pings. Sem isto, alternar app rapidinho (notificação,
 * responder mensagem, voltar) dispararia um ping por alternância. O Railway
 * dorme na casa dos minutos, então um ping por minuto já cobre. */
const INTERVALO_MIN_MS = 60_000;

let ultimoPing = 0;

export function aquecerBackend(): void {
  const agora = Date.now();
  if (agora - ultimoPing < INTERVALO_MIN_MS) return;
  ultimoPing = agora;
  // timeout curto: se o servidor está dormindo, esta chamada é justamente a que
  // vai falhar — e tudo bem, ela já cumpriu o papel de bater na porta.
  api.get("/health", { timeout: 8000 }).catch(() => {});
}

/** Liga o aquecimento ao ciclo de vida do app. Devolve a função de desligar. */
export function iniciarAquecimento(): () => void {
  aquecerBackend();
  const sub = AppState.addEventListener("change", (estado: AppStateStatus) => {
    if (estado === "active") aquecerBackend();
  });
  return () => sub.remove();
}
