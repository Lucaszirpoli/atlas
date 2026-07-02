import React, { useState } from "react";
import { Alert, Text, View } from "react-native";

import { applyManualGoal } from "../api/goals";
import { listMealCategories, logMeal } from "../api/meals";
import type { ProposedAction } from "../api/ai";
import { createRoutine } from "../api/routines";
import { logWeight } from "../api/weight";
import { useTheme } from "../theme/ThemeProvider";
import { Button } from "./Button";

export function ChatActionCard({
  action,
  onResolved,
}: {
  action: ProposedAction;
  onResolved: (outcome: "confirmed" | "cancelled") => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleConfirm() {
    setIsSubmitting(true);
    try {
      if (action.tool === "registrar_refeicao") {
        const items = (action.input.itens as any[]).filter((i) => i.food_id != null);
        if (items.length === 0) {
          Alert.alert("Não deu para confirmar", "Nenhum alimento foi reconhecido na base.");
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
      }
      onResolved("confirmed");
    } catch (err: any) {
      Alert.alert("Não foi possível confirmar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View
      style={{
        backgroundColor: colors.surface,
        borderRadius: radius.card,
        borderWidth: 1,
        borderColor: colors.primary,
        padding: spacing.md,
        marginTop: spacing.sm,
      }}
    >
      <Text style={[type.bodySmall, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        {describeAction(action)}
      </Text>
      <View style={{ flexDirection: "row", gap: spacing.sm }}>
        <View style={{ flex: 1 }}>
          <Button title="Confirmar" onPress={handleConfirm} loading={isSubmitting} />
        </View>
        <View style={{ flex: 1 }}>
          <Button title="Cancelar" variant="ghost" onPress={() => onResolved("cancelled")} />
        </View>
      </View>
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
  return "Confirmar ação";
}
