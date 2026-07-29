/** Ficha nutricional no formato do rótulo brasileiro (RDC 360/2003, ANVISA):
 * vírgula decimal, energia em kJ **e** kcal, e o "%IDR" — quanto aquela porção
 * representa da ingestão diária.
 *
 * O %IDR aqui divide pela META DE CALORIAS DA PESSOA, não pelos 2000 kcal fixos
 * do rótulo de embalagem: o app já sabe a meta real, e "4% da sua meta" diz
 * algo que "4% de uma dieta hipotética de 2000 kcal" não diz. Sem meta
 * definida, cai nos 2000 do padrão (ver utils/calorieTarget.ts).
 */

import { formatUnitLabel, gramasLegivel, parseDefaultPortion } from "./portion";

const KJ_POR_KCAL = 4.184;

export function kcalParaKj(kcal: number): number {
  return Math.round(kcal * KJ_POR_KCAL);
}

/** Número no padrão BR: vírgula decimal e sem zero à toa ("5g", não "5,00g"). */
export function numeroBr(n: number, casas = 2): string {
  if (!Number.isFinite(n)) return "0";
  const fixo = n.toFixed(casas);
  const limpo = casas > 0 ? fixo.replace(/\.?0+$/, "") : fixo;
  return limpo.replace(".", ",");
}

/** "4,97g" — sem espaço antes da unidade, como no rótulo. */
export function gramasBr(n: number | null | undefined, casas = 2): string {
  if (n == null) return "—";
  return `${numeroBr(n, casas)}g`;
}

export function miligramasBr(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${numeroBr(n, 0)}mg`;
}

/** Quanto essa quantidade de kcal representa da meta diária, em % inteiro. */
export function idrPercent(kcal: number, metaKcal: number): number {
  if (!metaKcal || metaKcal <= 0) return 0;
  return Math.round((kcal / metaKcal) * 100);
}

type ComPorcao = {
  default_portion_g: number;
  default_portion_label: string | null;
};

/** A porção de referência que aparece na linha do resultado de busca: a medida
 * caseira do alimento quando existe ("1 grande (50 g)"), senão as gramas
 * ("100 g"). É a mesma porção que já vem pré-selecionada ao abrir o alimento —
 * o número de kcal ao lado é sempre o DESSA porção, nunca por 100 g. */
export function porcaoDeReferencia(food: ComPorcao): { rotulo: string; gramas: number } {
  const gramas = food.default_portion_g ?? 100;
  const medida = parseDefaultPortion(food.default_portion_label, gramas);
  if (!medida) return { rotulo: `${gramasLegivel(gramas)} g`, gramas };
  return {
    rotulo: `${formatUnitLabel(medida.label, medida.amount)} (${gramasLegivel(gramas)} g)`,
    gramas,
  };
}

/** Escala um valor por-100g para a quantidade em gramas informada. */
export function por(valorPor100g: number | null | undefined, gramas: number): number | null {
  if (valorPor100g == null) return null;
  return (valorPor100g * gramas) / 100;
}
