import * as Print from "expo-print";
import * as Sharing from "expo-sharing";
import { Platform } from "react-native";

export type ExportableDiet = {
  name: string;
  tagline?: string;
  meals: { category: string; items: { food_name: string; quantity_g: number; kcal: number }[] }[];
  totals: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
};

function dietHtml(diet: ExportableDiet): string {
  const rows = diet.meals
    .map(
      (m) => `
        <h3>${m.category}</h3>
        <table>
          ${m.items
            .map(
              (i) =>
                `<tr><td>${i.food_name}</td><td>${Math.round(i.quantity_g)}g</td><td>${Math.round(i.kcal)} kcal</td></tr>`
            )
            .join("")}
        </table>`
    )
    .join("");

  return `
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body { font-family: -apple-system, Helvetica, Arial, sans-serif; color: #1A1A1A; padding: 24px; }
          h1 { font-size: 22px; margin-bottom: 2px; }
          .tagline { color: #666; margin-bottom: 16px; }
          .totals { display: flex; gap: 16px; background: #F3F3F3; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; }
          .totals div { text-align: center; }
          .totals b { display: block; font-size: 16px; }
          h3 { font-size: 15px; margin: 16px 0 6px; border-bottom: 1px solid #DDD; padding-bottom: 4px; }
          table { width: 100%; border-collapse: collapse; font-size: 13px; }
          td { padding: 3px 0; }
          td:last-child, td:nth-child(2) { text-align: right; color: #666; }
          .footer { margin-top: 24px; font-size: 11px; color: #999; }
        </style>
      </head>
      <body>
        <h1>${diet.name}</h1>
        ${diet.tagline ? `<div class="tagline">${diet.tagline}</div>` : ""}
        <div class="totals">
          <div><b>${Math.round(diet.totals.kcal)}</b>kcal</div>
          <div><b>${Math.round(diet.totals.protein_g)}g</b>proteína</div>
          <div><b>${Math.round(diet.totals.carbs_g)}g</b>carbo</div>
          <div><b>${Math.round(diet.totals.fat_g)}g</b>gordura</div>
        </div>
        ${rows}
        <div class="footer">Gerado pelo appfit — ponto de partida, não substitui orientação de um nutricionista.</div>
      </body>
    </html>`;
}

/** Exporta um plano de dieta (pronto ou montado pela IA) como PDF. Na web abre
 * o diálogo de impressão do navegador (a pessoa escolhe "Salvar como PDF");
 * no app nativo gera o arquivo e abre o menu de compartilhar/salvar. */
export async function exportDietAsPdf(diet: ExportableDiet): Promise<void> {
  const html = dietHtml(diet);
  if (Platform.OS === "web") {
    await Print.printAsync({ html });
    return;
  }
  const { uri } = await Print.printToFileAsync({ html });
  await Sharing.shareAsync(uri, { mimeType: "application/pdf", dialogTitle: diet.name });
}
