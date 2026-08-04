import AsyncStorage from "@react-native-async-storage/async-storage";

import type { DietPlan } from "../../api/ai";
import type { CoachChatAction, CoachChatMessage } from "../../api/coaching";

/**
 * MEMÓRIA DA CONVERSA com o coach, no aparelho.
 *
 * O bug: a conversa vivia só no `useState` da tela. Sair do chat e voltar
 * apagava tudo — a pessoa contava a semana inteira, pedia um ajuste, saía pra
 * conferir o treino, voltava, e o coach não fazia ideia de quem ela era. Pior:
 * como o histórico enviado ao servidor sai daqui, o coach perdia o contexto
 * junto (a resposta a "e o segundo exercício?" dependia da mensagem anterior).
 *
 * Fica no armazenamento LOCAL, de propósito: conversa sobre corpo, lesão e
 * comida é dado sensível (LGPD), e o servidor não precisa de uma cópia pra o
 * produto funcionar. O que ele já guarda são os EFEITOS (o treino trocado, a
 * refeição registrada) — não o desabafo.
 *
 * Guardar por usuário evita o pior modo de falha deste arquivo: trocar de conta
 * no mesmo aparelho e ver a conversa de outra pessoa.
 */

const PREFIX = "coach_chat:";

/** Teto de mensagens guardadas. O chat manda as últimas 8 pro servidor; o resto
 * é memória pra pessoa reler. 200 cobre meses de uso sem inchar o storage. */
const MAX_MENSAGENS = 200;

export type ChatBubble = CoachChatMessage & {
  actions?: CoachChatAction[];
  dietPlan?: DietPlan | null;
};

function key(userId: number | string): string {
  return `${PREFIX}${userId}`;
}

export async function loadChat(userId: number | string): Promise<ChatBubble[]> {
  try {
    const bruto = await AsyncStorage.getItem(key(userId));
    if (!bruto) return [];
    const dados = JSON.parse(bruto);
    if (!Array.isArray(dados)) return [];
    // Filtra o que não é mensagem: um storage corrompido não pode derrubar a
    // tela do coach — pior caso, a conversa volta vazia.
    return dados.filter(
      (m: any) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string"
    );
  } catch {
    return [];
  }
}

export async function saveChat(userId: number | string, mensagens: ChatBubble[]): Promise<void> {
  try {
    await AsyncStorage.setItem(key(userId), JSON.stringify(mensagens.slice(-MAX_MENSAGENS)));
  } catch {
    // Armazenamento cheio/indisponível: perder a memória da conversa é ruim,
    // mas quebrar o chat por causa disso é pior.
  }
}

export async function clearChat(userId: number | string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key(userId));
  } catch {
    /* idem */
  }
}
