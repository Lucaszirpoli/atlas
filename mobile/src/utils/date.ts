/** Data local (YYYY-MM-DD) de HOJE — sem escorregar de fuso como
 * `new Date().toISOString().slice(0,10)` faz perto da meia-noite (esse usa
 * UTC; isto usa o relógio do aparelho). */
export function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** ("2026-07-20", -1) -> "2026-07-19". Soma dias em data local, sem UTC. */
export function addDaysIso(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** "2026-07-20" -> "Hoje" / "Ontem" / "20 de julho". */
export function diaLabel(iso: string): string {
  const hoje = isoToday();
  if (iso === hoje) return "Hoje";
  if (iso === addDaysIso(hoje, -1)) return "Ontem";
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString("pt-BR", { day: "numeric", month: "long" });
}
