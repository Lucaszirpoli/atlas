/** Meta calórica diária da pessoa, para o "%IDR" da ficha nutricional.
 *
 * Cacheada em memória por dois motivos: a busca de alimentos renderiza dezenas
 * de linhas que precisam do mesmo número, e a meta muda raramente (só quando o
 * usuário mexe em Objetivo/Meta calórica). Quem alterar a meta chama
 * `invalidarMetaCalorica()` pra próxima leitura buscar de novo.
 */

import { useEffect, useState } from "react";

import { getCurrentGoal } from "../api/goals";

/** Referência do rótulo de embalagem (ANVISA). Só entra quando a pessoa ainda
 * não definiu meta nenhuma — assim o %IDR nunca fica vazio na tela. */
export const KCAL_REFERENCIA_PADRAO = 2000;

let cache: number | null = null;
let emVoo: Promise<number> | null = null;

function buscar(): Promise<number> {
  if (emVoo) return emVoo;
  emVoo = getCurrentGoal()
    .then((meta) => {
      const kcal = meta?.kcal && meta.kcal > 0 ? meta.kcal : KCAL_REFERENCIA_PADRAO;
      cache = kcal;
      return kcal;
    })
    .catch(() => KCAL_REFERENCIA_PADRAO)
    .finally(() => {
      emVoo = null;
    });
  return emVoo;
}

export function invalidarMetaCalorica(): void {
  cache = null;
}

/** Meta diária em kcal. Devolve o padrão enquanto a real não chegou — a linha
 * do alimento nunca fica sem número, só reajusta o % quando a meta carrega. */
export function useMetaCalorica(): number {
  const [meta, setMeta] = useState(cache ?? KCAL_REFERENCIA_PADRAO);

  useEffect(() => {
    if (cache != null) {
      setMeta(cache);
      return;
    }
    let vivo = true;
    buscar().then((kcal) => {
      if (vivo) setMeta(kcal);
    });
    return () => {
      vivo = false;
    };
  }, []);

  return meta;
}
