import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Ordem dos cards da tela de Coaching, salva NO APARELHO.
 *
 * Fica local de propósito: é preferência de layout, não dado de saúde — não
 * precisa de tabela nem sincronizar entre aparelhos.
 */

const CHAVE = "@appfit/coaching_card_order";

export type CoachingCardId =
  | "objetivo"
  | "como_monto"
  | "seu_treino"
  | "pergunte_coach"
  | "checkin"
  | "tudo_certo"
  | "o_que_mudou"
  | "seus_dados";

export const DEFAULT_CARD_ORDER: CoachingCardId[] = [
  "objetivo",
  "como_monto",
  "seu_treino",
  "pergunte_coach",
  "checkin",
  "tudo_certo",
  "o_que_mudou",
  "seus_dados",
];

// Todos os cards reordenam num grupo ÚNICO — sem barreira. As barras de
// sugestão (geradas pela análise, não cards) ficam fixas no topo; qualquer card
// pode ser movido pra qualquer posição em relação aos outros.

export async function loadCardOrder(): Promise<CoachingCardId[]> {
  try {
    const cru = await AsyncStorage.getItem(CHAVE);
    if (!cru) return DEFAULT_CARD_ORDER;
    const salvo: string[] = JSON.parse(cru);
    if (!Array.isArray(salvo)) return DEFAULT_CARD_ORDER;
    // Reconcilia com o padrão: mantém a ordem salva, mas inclui qualquer card
    // novo que o app tenha ganhado depois (no fim) e descarta ids que sumiram.
    const validos = salvo.filter((id): id is CoachingCardId => DEFAULT_CARD_ORDER.includes(id as CoachingCardId));
    const faltando = DEFAULT_CARD_ORDER.filter((id) => !validos.includes(id));
    return [...validos, ...faltando];
  } catch {
    return DEFAULT_CARD_ORDER;
  }
}

export async function saveCardOrder(order: CoachingCardId[]): Promise<void> {
  try {
    await AsyncStorage.setItem(CHAVE, JSON.stringify(order));
  } catch {
    // Falhar em salvar a ordem não pode atrapalhar o uso da tela.
  }
}
