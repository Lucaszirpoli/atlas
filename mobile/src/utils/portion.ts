/** Formatação de medidas caseiras (gramas/unidades).
 *
 * Guardamos o rótulo da unidade sempre no SINGULAR ("fatia", "colher de sopa",
 * "unidade"); a pluralização acontece só na exibição. A base de todo cálculo
 * nutricional continua sendo as gramas — a unidade é só a forma humana de
 * escolher/mostrar a quantidade.
 */

/** Pluraliza a PRIMEIRA palavra da medida ("colher de sopa" -> "colheres de
 * sopa"), não o fim da frase — o substantivo que varia é o primeiro. */
export function pluralizar(medida: string): string {
  const [primeira, ...resto] = medida.split(" ");
  let p = primeira;
  if (primeira.endsWith("s")) p = primeira; // já plural
  else if (primeira.endsWith("ão")) p = primeira.slice(0, -2) + "ões";
  else if (/[rz]$/.test(primeira)) p = primeira + "es"; // colher -> colheres
  else p = primeira + "s"; // concha -> conchas, fatia -> fatias
  return [p, ...resto].join(" ");
}

/** "fatia" + 2 -> "2 fatias"; + 0.5 -> "½ fatia"; + 1 -> "1 fatia". */
export function formatUnitLabel(label: string, amount: number): string {
  if (amount === 0.5) return `½ ${label}`;
  const inteiro = Number.isInteger(amount) ? String(amount) : amount.toFixed(1).replace(".", ",");
  return `${inteiro} ${amount > 1 ? pluralizar(label) : label}`;
}

/** Arredonda gramas pra exibição: sem casa decimal desnecessária. */
export function gramasLegivel(g: number): string {
  return (Math.round(g * 10) / 10).toString().replace(".", ",");
}

/** Como mostrar a quantidade registrada de um item.
 * Com unidade: "2 fatias · 50 g". Só gramas: "150 g". */
export function formatQuantity(
  quantityG: number,
  unitLabel: string | null | undefined,
  unitAmount: number | null | undefined
): string {
  if (unitLabel && unitAmount) {
    return `${formatUnitLabel(unitLabel, unitAmount)} · ${gramasLegivel(quantityG)} g`;
  }
  return `${gramasLegivel(quantityG)} g`;
}
