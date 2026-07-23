/** Formata um peso em kg pra exibição — arredonda a 1 casa e mata o ruído de
 * ponto flutuante (54.599999999999994 → "54,6", 40 → "40"). Vírgula decimal
 * (pt-BR). */
export function fmtKg(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  const rounded = Math.round(n * 10) / 10;
  return (Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1)).replace(".", ",");
}
