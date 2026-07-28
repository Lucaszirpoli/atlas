import AsyncStorage from "@react-native-async-storage/async-storage";

import type { SetRow } from "./techniqueSets";

/**
 * RASCUNHO do treino ativo (spec §8.2).
 *
 * O bug: a pessoa anotava carga e reps, saía da aba (ver uma receita, responder
 * uma mensagem, tela bloqueou) e voltava com tudo em branco. No meio de um
 * treino isso é imperdoável — os números que ela pegou naquele dia não existem
 * em nenhum outro lugar.
 *
 * A regra aqui é gravar LOCALMENTE a cada alteração, na hora, sem depender de
 * rede. O servidor já guarda cada série confirmada; o rascunho guarda o que
 * ainda NÃO foi confirmado (o que está digitado, os blocos marcados, qual
 * exercício estava aberto) — que é justamente o que se perdia.
 *
 * O rascunho só é apagado quando o treino termina, é descartado ou cancelado
 * com confirmação. Nunca por sair da tela.
 */

const PREFIX = "workout_draft:";

export type WorkoutDraft = {
  sessionId: number;
  setsByExercise: SetRow[][];
  /** Índice do exercício que estava aberto/visível, pra voltar no mesmo lugar. */
  openExercise?: number;
  savedAt: number;
};

function key(sessionId: number): string {
  return `${PREFIX}${sessionId}`;
}

export async function saveDraft(
  sessionId: number,
  setsByExercise: SetRow[][],
  openExercise?: number
): Promise<void> {
  try {
    const draft: WorkoutDraft = { sessionId, setsByExercise, openExercise, savedAt: Date.now() };
    await AsyncStorage.setItem(key(sessionId), JSON.stringify(draft));
  } catch {
    // Armazenamento cheio/indisponível: não dá pra atrapalhar o treino por
    // causa disso. O que já foi confirmado continua salvo no servidor.
  }
}

export async function loadDraft(sessionId: number): Promise<WorkoutDraft | null> {
  try {
    const raw = await AsyncStorage.getItem(key(sessionId));
    if (!raw) return null;
    const draft = JSON.parse(raw) as WorkoutDraft;
    if (!Array.isArray(draft?.setsByExercise)) return null;
    return draft;
  } catch {
    return null;
  }
}

/** Só ao concluir, descartar ou cancelar com confirmação — nunca ao sair da tela. */
export async function clearDraft(sessionId: number): Promise<void> {
  try {
    await AsyncStorage.removeItem(key(sessionId));
  } catch {
    /* sem storage: nada a limpar */
  }
}

/** Varre rascunhos órfãos (sessões antigas que nunca foram fechadas) pra o
 * armazenamento não crescer pra sempre. Roda no fim de um treino, quando não
 * há pressa. Mantém qualquer rascunho com menos de 2 dias. */
export async function purgeOldDrafts(maxAgeMs = 2 * 24 * 3600 * 1000): Promise<void> {
  try {
    const keys = (await AsyncStorage.getAllKeys()).filter((k) => k.startsWith(PREFIX));
    if (keys.length === 0) return;
    const agora = Date.now();
    const velhos: string[] = [];
    for (const [k, raw] of await AsyncStorage.multiGet(keys)) {
      if (!raw) continue;
      try {
        const d = JSON.parse(raw) as WorkoutDraft;
        if (agora - (d.savedAt ?? 0) > maxAgeMs) velhos.push(k);
      } catch {
        velhos.push(k); // ilegível: não serve mais pra nada
      }
    }
    if (velhos.length) await AsyncStorage.multiRemove(velhos);
  } catch {
    /* melhor esforço */
  }
}
