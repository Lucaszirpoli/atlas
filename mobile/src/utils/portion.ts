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

const ROTULOS_GENERICOS = new Set(["porção", "porcao", "medida", "g", "grama", "gramas"]);

/** Singulariza a PRIMEIRA palavra da medida ("colheres de sopa" -> "colher de
 * sopa") — o inverso de pluralizar(), usado ao derivar a medida embutida de um
 * alimento a partir do seu default_portion_label. Espelha
 * backend/app/scripts/seed_food_portions.py::_singular_primeira. */
function singularPrimeira(frase: string): string {
  const palavras = frase.split(" ");
  if (palavras.length === 0) return frase;
  let w = palavras[0];
  if (w.endsWith("ões")) w = w.slice(0, -3) + "ão";
  else if (w.endsWith("es") && w.length > 3 && /[rz]/.test(w[w.length - 3])) w = w.slice(0, -2);
  else if (w.endsWith("s") && w.length > 2) w = w.slice(0, -1);
  return [w, ...palavras.slice(1)].join(" ");
}

/** ("1 unidade", 50) -> {label:"unidade", grams:50, amount:1}.
 * ("3 colheres de sopa", 45) -> {label:"colher de sopa", grams:15, amount:3}.
 * null quando não dá pra derivar uma medida útil (mesmas regras do backend,
 * que já embute essa medida como FoodPortion — replicar aqui deixa a unidade
 * certa pré-selecionada na hora, sem esperar a busca das medidas do alimento). */
export function parseDefaultPortion(
  label: string | null | undefined,
  portionG: number | null | undefined
): { label: string; grams: number; amount: number } | null {
  if (!label || !portionG || portionG <= 0) return null;
  const texto = label.trim();
  const m = texto.match(/^\s*(\d+(?:[.,]\d+)?)\s+(.*\S)\s*$/);
  let n: number;
  let frase: string;
  if (m) {
    n = parseFloat(m[1].replace(",", "."));
    frase = m[2];
  } else {
    n = 1;
    frase = texto;
  }
  if (!(n > 0) || !frase) return null;
  const gramsOne = portionG / n;
  if (!(gramsOne > 0) || gramsOne > 5000) return null;
  if (n !== 1) frase = singularPrimeira(frase);
  if (ROTULOS_GENERICOS.has(frase.toLowerCase())) return null;
  return { label: frase.slice(0, 50), grams: Math.round(gramsOne * 100) / 100, amount: n };
}

/** Quantidade inicial ao adicionar um alimento pela primeira vez: usa a medida
 * caseira derivada do default_portion_label quando existe (ninguém pensa em
 * "ovo" como 50 gramas — pensa em "1 unidade"), senão cai pras gramas. */
export function initialQuantityFor(food: {
  default_portion_g: number;
  default_portion_label: string | null;
}): { quantity_g: number; unit_label: string | null; unit_amount: number | null } {
  const portionG = food.default_portion_g ?? 100;
  const parsed = parseDefaultPortion(food.default_portion_label, portionG);
  if (parsed) {
    return { quantity_g: portionG, unit_label: parsed.label, unit_amount: parsed.amount };
  }
  return { quantity_g: portionG, unit_label: null, unit_amount: null };
}
