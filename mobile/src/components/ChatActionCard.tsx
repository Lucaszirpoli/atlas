import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { Text, View } from "react-native";

import type { ProposedAction } from "../api/ai";
import { applyManualGoal } from "../api/goals";
import { listMealCategories, listMealsForDay, logMeal } from "../api/meals";
import { createRoutine, createRoutinesBulk } from "../api/routines";
import { logWeight } from "../api/weight";
import { exportDietAsPdf } from "../utils/pdfExport";
import { useTheme } from "../theme/ThemeProvider";
import { Button } from "./Button";
import { InfoDialog } from "./InfoDialog";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** A IA às vezes serializa a lista (rotinas/exercícios/refeições) como uma
 * STRING de JSON em vez de array — o backend já se defende disso, e aqui a
 * gente aceita os dois formatos pra a confirmação não quebrar calada. */
function asArray(v: unknown): unknown[] {
  if (Array.isArray(v)) return v;
  if (typeof v === "string") {
    try {
      const parsed = JSON.parse(v);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

export function ChatActionCard({
  action,
  onResolved,
}: {
  action: ProposedAction;
  onResolved: (outcome: "confirmed" | "cancelled") => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [confirmedDiet, setConfirmedDiet] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function handleConfirm() {
    setIsSubmitting(true);
    try {
      if (action.tool === "registrar_refeicao") {
        const items = (action.input.itens as any[]).filter((i) => i.food_id != null);
        if (items.length === 0) {
          setErrorMsg("Nenhum alimento foi reconhecido na base.");
          onResolved("cancelled");
          return;
        }
        const categories = await listMealCategories();
        const match =
          categories.find(
            (c) => c.name.toLowerCase() === String(action.input.categoria).toLowerCase()
          ) ?? categories[0];
        await logMeal({
          meal_category_id: match.id,
          logged_at: new Date().toISOString(),
          items: items.map((i) => ({ food_id: i.food_id, quantity_g: i.quantidade_g })),
        });
      } else if (action.tool === "atualizar_peso") {
        await logWeight(action.input.peso_kg);
      } else if (action.tool === "ajustar_meta_calorica") {
        await applyManualGoal({
          kcal: action.input.kcal,
          protein_g: action.input.protein_g,
          carbs_g: action.input.carbs_g,
          fat_g: action.input.fat_g,
        });
      } else if (action.tool === "criar_rotina_treino") {
        await createRoutine({
          name: action.input.nome,
          exercises: (action.input.exercicios as any[]).map((e) => ({
            exercise_id: e.exercise_id,
            target_sets: e.target_sets,
            target_reps_min: e.target_reps_min,
            target_reps_max: e.target_reps_max ?? null,
            rest_seconds: e.rest_seconds ?? 90,
          })),
        });
      } else if (action.tool === "criar_dieta_personalizada") {
        const refeicoes = (action.input.refeicoes as any[]) ?? [];
        const categories = await listMealCategories();
        for (const refeicao of refeicoes) {
          const items = (refeicao.itens as any[]).filter((i) => i.food_id != null);
          if (items.length === 0) continue;
          const match =
            categories.find((c) => c.name.toLowerCase() === String(refeicao.categoria).toLowerCase()) ??
            categories[0];
          await logMeal({
            meal_category_id: match.id,
            logged_at: new Date().toISOString(),
            items: items.map((i) => ({ food_id: i.food_id, quantity_g: i.quantidade_g })),
          });
        }
        setConfirmedDiet(true);
        setIsSubmitting(false);
        return; // fica aberto mostrando "Baixar PDF" — só fecha quando a pessoa tocar em "Concluir"
      } else if (action.tool === "criar_treino_personalizado") {
        // UMA chamada atômica (arquiva + cria tudo). Antes eram N chamadas
        // soltas: qualquer uma falhando deixava o treino pela metade e só
        // aparecia "tente novamente", sem dizer o que quebrou.
        const rotinas = (asArray(action.input.rotinas) as any[]).map((r) => ({
          nome: String(r?.nome ?? "Treino"),
          exercicios: (asArray(r?.exercicios) as any[])
            .filter((e) => Number.isFinite(Number(e?.exercise_id)))
            .map((e) => ({
              exercise_id: Number(e.exercise_id),
              target_sets: Number(e.target_sets) || 3,
              target_reps_min: Number(e.target_reps_min) || 8,
              target_reps_max: e.target_reps_max != null ? Number(e.target_reps_max) : null,
              rest_seconds: Number(e.rest_seconds) || 90,
            })),
        }));
        if (rotinas.length === 0) {
          setErrorMsg("Não recebi o treino da IA direito. Peça pra ela montar de novo.");
          setIsSubmitting(false);
          return;
        }
        const res = await createRoutinesBulk({
          rotinas,
          substituir_existentes: Boolean(action.input.substituir_existentes),
        });
        if (res.skipped_exercises.length > 0) {
          setErrorMsg(
            `Treino salvo (${res.created} ${res.created === 1 ? "rotina" : "rotinas"}), mas ${res.skipped_exercises.length} exercício(s) não existiam na base e ficaram de fora.`
          );
        }
      }
      onResolved("confirmed");
    } catch (err: any) {
      // Mostra a causa REAL (o backend manda um detail explicativo).
      const detail = err?.response?.data?.detail;
      setErrorMsg(
        typeof detail === "string" && detail
          ? detail
          : err?.message
            ? `Falhou: ${err.message}`
            : "Tente novamente."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDownloadDiet() {
    if (downloading) return;
    setDownloading(true);
    try {
      const meals = await listMealsForDay(todayIso());
      const byCategory = new Map<string, { food_name: string; quantity_g: number; kcal: number }[]>();
      const categories = await listMealCategories();
      const nameById = new Map(categories.map((c) => [c.id, c.name]));
      let totals = { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 };
      for (const meal of meals) {
        const catName = nameById.get(meal.meal_category_id) ?? "Refeição";
        const list = byCategory.get(catName) ?? [];
        for (const item of meal.items) {
          list.push({ food_name: item.food.name, quantity_g: item.quantity_g, kcal: item.kcal });
          totals = {
            kcal: totals.kcal + item.kcal,
            protein_g: totals.protein_g + item.protein_g,
            carbs_g: totals.carbs_g + item.carbs_g,
            fat_g: totals.fat_g + item.fat_g,
          };
        }
        byCategory.set(catName, list);
      }
      await exportDietAsPdf({
        name: action.input.nome_do_plano || "Sua dieta personalizada",
        tagline: "Montada pela IA do Atlas, registrada hoje",
        meals: Array.from(byCategory.entries()).map(([category, items]) => ({ category, items })),
        totals,
      });
    } finally {
      setDownloading(false);
    }
  }

  return (
    <View
      style={{
        backgroundColor: colors.primarySoft,
        borderRadius: radius.card,
        borderWidth: 1.5,
        borderColor: colors.primary,
        padding: spacing.md,
        marginTop: spacing.sm,
      }}
    >
      <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, marginBottom: 4 }]}>
        AÇÃO SUGERIDA · VOCÊ DECIDE
      </Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary, marginBottom: spacing.md }]}>
        {describeAction(action)}
      </Text>
      {confirmedDiet ? (
        <View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginBottom: spacing.md }}>
            <Ionicons name="checkmark-circle" size={14} color={colors.primary} />
            <Text style={[type.caption, { color: colors.primary }]}>Registrado no seu diário de hoje</Text>
          </View>
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <View style={{ flex: 1 }}>
              <Button title="Baixar PDF" variant="ghost" compact onPress={handleDownloadDiet} loading={downloading} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title="Concluir" compact onPress={() => onResolved("confirmed")} />
            </View>
          </View>
        </View>
      ) : (
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <View style={{ flex: 1 }}>
            <Button title="Confirmar" compact onPress={handleConfirm} loading={isSubmitting} />
          </View>
          <View style={{ flex: 1 }}>
            <Button title="Agora não" variant="ghost" compact onPress={() => onResolved("cancelled")} />
          </View>
        </View>
      )}
      <InfoDialog
        visible={errorMsg !== null}
        onClose={() => setErrorMsg(null)}
        title="Não foi possível confirmar"
        message={errorMsg ?? undefined}
      />
    </View>
  );
}

function describeAction(action: ProposedAction): string {
  if (action.tool === "registrar_refeicao") {
    const itens = (action.input.itens as any[]).map((i) => `${i.nome} (${i.quantidade_g}g)`).join(", ");
    return `Registrar em ${action.input.categoria}: ${itens}`;
  }
  if (action.tool === "atualizar_peso") {
    return `Registrar novo peso: ${action.input.peso_kg}kg`;
  }
  if (action.tool === "ajustar_meta_calorica") {
    return `Nova meta: ${action.input.kcal}kcal · P${action.input.protein_g}g · C${action.input.carbs_g}g · G${action.input.fat_g}g`;
  }
  if (action.tool === "criar_rotina_treino") {
    const exercicios = (action.input.exercicios as any[])
      .map((e) => `${e.nome} (${e.target_sets}x${e.target_reps_min}${e.target_reps_max ? `-${e.target_reps_max}` : ""})`)
      .join(", ");
    return `Criar rotina "${action.input.nome}": ${exercicios}`;
  }
  if (action.tool === "criar_dieta_personalizada") {
    const refeicoes = (action.input.refeicoes as any[]) ?? [];
    const totalItens = refeicoes.reduce((s, r) => s + (r.itens?.length ?? 0), 0);
    const linhas = refeicoes
      .map((r) => `${r.categoria}: ${(r.itens as any[]).map((i) => `${i.nome} (${i.quantidade_g}g)`).join(", ")}`)
      .join("\n");
    return `Registrar dieta de hoje (${refeicoes.length} refeições, ${totalItens} alimentos):\n${linhas}`;
  }
  if (action.tool === "criar_treino_personalizado") {
    const rotinas = (action.input.rotinas as any[]) ?? [];
    const nomes = rotinas.map((r) => `"${r.nome}" (${r.exercicios.length} exercícios)`).join(", ");
    const sub = action.input.substituir_existentes
      ? " — vai arquivar suas rotinas ativas atuais antes de criar as novas."
      : " — mantém suas rotinas atuais e adiciona estas.";
    return `Criar treino: ${nomes}.${sub}`;
  }
  return "Confirmar ação";
}
