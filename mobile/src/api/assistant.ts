import type { ProposedAction } from "./ai";
import { api } from "./client";

export type AssistantReply = {
  reply: string;
  answered: boolean;
  /** "app" = respondido de graça pelo motor determinístico | "ai" = veio da IA (Claude). */
  source?: "app" | "ai";
  /** Créditos-isca de IA restantes do plano Free (null/ausente = Pro/ilimitado). */
  credits_left?: number | null;
  /** Ação que a IA propôs (ex: criar dieta/treino) — precisa confirmação antes de salvar. */
  proposed_action?: ProposedAction | null;
};

/** Assistente híbrido: tenta o motor determinístico (grátis, sem token) e, se
 * ele não souber, cai na IA (Claude) — ilimitada no Pro, com créditos no Free. */
export async function askAssistant(text: string): Promise<AssistantReply> {
  // A IA (Claude) pode levar mais que os 15s padrão do axios — 90s de folga
  // pra não abortar uma resposta que o backend ainda está gerando.
  const { data } = await api.post("/assistant/ask", { text }, { timeout: 90000 });
  return data;
}
