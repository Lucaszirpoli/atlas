import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { Platform } from "react-native";

import type { DietPlan } from "../api/ai";

// Documento HTML da dieta — vira o PDF. Marca ATLAS (preto + laranja #FF6B2C).
function dietHtml(plan: DietPlan): string {
  const t = plan.totals;
  const meta = plan.target;
  const linhaMacros = (o: { kcal: number; protein_g: number; carbs_g: number; fat_g: number }) =>
    `${Math.round(o.kcal)} kcal · P ${Math.round(o.protein_g)}g · C ${Math.round(o.carbs_g)}g · G ${Math.round(o.fat_g)}g`;

  const refeicoes = plan.meals
    .map((m) => {
      const itens = m.items
        .map(
          (it) => `
          <tr>
            <td>${it.food_name}</td>
            <td class="r">${Math.round(it.quantity_g)} g</td>
            <td class="r">${Math.round(it.kcal)} kcal</td>
          </tr>`
        )
        .join("");
      return `
        <div class="meal">
          <h3>${m.category}</h3>
          <table>${itens}</table>
        </div>`;
    })
    .join("");

  const restr = plan.restrictions.length
    ? `<p class="sub">Restrições consideradas: ${plan.restrictions.join(", ")}</p>`
    : "";

  return `<!doctype html><html><head><meta charset="utf-8"/>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; color: #16181D; margin: 40px; }
    .brand { color: #FF6B2C; font-weight: 800; letter-spacing: 2px; font-size: 13px; }
    h1 { font-size: 24px; margin: 4px 0 2px; }
    .sub { color: #6B7280; font-size: 12px; margin: 2px 0; }
    .totais { background: #FFF3EC; border: 1px solid #FFD9C2; border-radius: 10px; padding: 12px 16px; margin: 16px 0 8px; }
    .totais b { color: #FF6B2C; }
    .meal { margin-top: 18px; }
    .meal h3 { font-size: 15px; margin: 0 0 6px; border-bottom: 2px solid #16181D; padding-bottom: 4px; }
    table { width: 100%; border-collapse: collapse; }
    td { padding: 5px 0; font-size: 13px; border-bottom: 1px solid #EEE; }
    td.r { text-align: right; color: #6B7280; white-space: nowrap; padding-left: 12px; }
    .foot { margin-top: 28px; color: #9CA3AF; font-size: 11px; }
  </style></head><body>
    <div class="brand">ATLAS · COACHING</div>
    <h1>Sua dieta personalizada</h1>
    <div class="totais">
      <div><b>Total do dia:</b> ${linhaMacros(t)}</div>
      <p class="sub">Meta: ${linhaMacros(meta)}</p>
      ${restr}
    </div>
    ${refeicoes}
    <p class="foot">Gerado pelo coach do ATLAS. Ajuste as porções ao seu paladar — o que importa é bater os macros do dia.</p>
  </body></html>`;
}

/** Exporta a dieta como PDF. No app nativo, gera o arquivo e abre o menu de
 * compartilhar/salvar; no web, abre o diálogo de impressão (salvar como PDF). */
export async function exportDietPdf(plan: DietPlan): Promise<void> {
  const html = dietHtml(plan);
  if (Platform.OS === "web") {
    await Print.printAsync({ html });
    return;
  }
  const { uri } = await Print.printToFileAsync({ html });
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(uri, { mimeType: "application/pdf", dialogTitle: "Salvar dieta em PDF", UTI: "com.adobe.pdf" });
  }
}
