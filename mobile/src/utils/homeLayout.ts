import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";

/**
 * Ordem dos blocos da home (Coaching), salva NO APARELHO.
 *
 * Fica local de propósito: é preferência de layout, não dado de saúde — não
 * precisa de tabela nem sincronizar entre aparelhos. O cabeçalho (saudação +
 * avatar + Desafios/Amigos) fica sempre fixo no topo; só o conteúdo do coach
 * abaixo dele é reordenável.
 */

export type HomeBlockId =
  | "hero"
  | "missoes"
  | "tudo_certo"
  | "aprendizado"
  | "explorar"
  | "pergunte_coach"
  | "o_que_mudou";

export const DEFAULT_HOME_ORDER: HomeBlockId[] = [
  "hero",
  "missoes",
  "tudo_certo",
  "aprendizado",
  "explorar",
  "pergunte_coach",
  "o_que_mudou",
];

export const HOME_BLOCK_META: Record<
  HomeBlockId,
  { label: string; description: string; icon: string }
> = {
  hero: { label: "Seu coaching", description: "Objetivo, fase e constância", icon: "compass" },
  missoes: { label: "Missões da semana", description: "O que precisa de atenção agora", icon: "flag" },
  tudo_certo: { label: "Tudo certo", description: "O que já está indo bem", icon: "checkmark-circle" },
  aprendizado: {
    label: "O que eu aprendi com você",
    description: "Os números que medi em você e já uso no seu plano",
    icon: "school",
  },
  explorar: { label: "Explorar", description: "Objetivo, treino, dieta, peso e sono", icon: "grid" },
  pergunte_coach: { label: "Pergunte ao coach", description: "Atalho pro chat", icon: "chatbubbles" },
  o_que_mudou: { label: "O que o coach mudou", description: "Ajustes aplicados e histórico", icon: "time" },
};

const CHAVE = "@appfit/home_block_order";

export async function loadHomeOrder(): Promise<HomeBlockId[]> {
  try {
    const cru = await AsyncStorage.getItem(CHAVE);
    if (!cru) return DEFAULT_HOME_ORDER;
    const salvo: string[] = JSON.parse(cru);
    if (!Array.isArray(salvo)) return DEFAULT_HOME_ORDER;
    // Reconcilia com o padrão: mantém a ordem salva, mas inclui qualquer bloco
    // novo que o app tenha ganhado depois (no fim) e descarta ids que sumiram.
    const validos = salvo.filter((id): id is HomeBlockId => DEFAULT_HOME_ORDER.includes(id as HomeBlockId));
    const faltando = DEFAULT_HOME_ORDER.filter((id) => !validos.includes(id));
    return [...validos, ...faltando];
  } catch {
    return DEFAULT_HOME_ORDER;
  }
}

export async function saveHomeOrder(order: HomeBlockId[]): Promise<void> {
  try {
    await AsyncStorage.setItem(CHAVE, JSON.stringify(order));
  } catch {
    // Falhar em salvar a ordem não pode atrapalhar o uso da tela.
  }
}

export async function resetHomeOrder(): Promise<void> {
  try {
    await AsyncStorage.removeItem(CHAVE);
  } catch {
    // idem
  }
}

/** Hook: ordem atual + mover um bloco pra cima/baixo + restaurar padrão.
 * Recarrega a ordem salva sempre que `reload()` é chamado (ex: no foco da
 * tela, pra Home pegar o que foi mudado em Configurações). */
export function useHomeLayout() {
  const [order, setOrder] = useState<HomeBlockId[]>(DEFAULT_HOME_ORDER);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    loadHomeOrder().then((o) => {
      if (!cancelled) {
        setOrder(o);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => reload(), [reload]);

  const move = useCallback((id: HomeBlockId, direction: -1 | 1) => {
    setOrder((atual) => {
      const idx = atual.indexOf(id);
      const alvo = idx + direction;
      if (idx < 0 || alvo < 0 || alvo >= atual.length) return atual;
      const proximo = [...atual];
      [proximo[idx], proximo[alvo]] = [proximo[alvo], proximo[idx]];
      saveHomeOrder(proximo);
      return proximo;
    });
  }, []);

  const resetToDefault = useCallback(() => {
    setOrder(DEFAULT_HOME_ORDER);
    resetHomeOrder();
  }, []);

  /** Define a ordem inteira de uma vez (arrastar-e-soltar na home, em vez de
   * mover um bloco de cada vez com as setinhas). */
  const reorder = useCallback((novaOrdem: HomeBlockId[]) => {
    setOrder(novaOrdem);
    saveHomeOrder(novaOrdem);
  }, []);

  return { order, loading, move, reorder, resetToDefault, reload };
}
