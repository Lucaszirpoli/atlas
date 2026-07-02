import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import {
  applyAutoGoal,
  applyManualGoal,
  getAutoSuggestion,
  getCurrentGoal,
  type CalorieGoal,
  type CalorieGoalSuggestion,
} from "../../api/goals";
import { Button } from "../../components/Button";
import { useTheme } from "../../theme/ThemeProvider";

export function GoalSettingsScreen() {
  const { colors, type, spacing, radius } = useTheme();

  const [currentGoal, setCurrentGoal] = useState<CalorieGoal | null>(null);
  const [suggestion, setSuggestion] = useState<CalorieGoalSuggestion | null>(null);
  const [manualKcal, setManualKcal] = useState("");
  const [manualProtein, setManualProtein] = useState("");
  const [manualCarbs, setManualCarbs] = useState("");
  const [manualFat, setManualFat] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function load() {
    setIsLoading(true);
    try {
      const [goal, autoSuggestion] = await Promise.all([
        getCurrentGoal(),
        getAutoSuggestion().catch(() => null),
      ]);
      setCurrentGoal(goal);
      setSuggestion(autoSuggestion);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleApplyAuto() {
    setIsSubmitting(true);
    try {
      const goal = await applyAutoGoal();
      setCurrentGoal(goal);
      Alert.alert("Meta atualizada", "Sua meta calórica foi recalculada.");
    } catch (err: any) {
      Alert.alert("Não foi possível calcular", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleApplyManual() {
    const kcal = Number(manualKcal);
    const protein = Number(manualProtein);
    const carbs = Number(manualCarbs);
    const fat = Number(manualFat);
    if (!kcal || !protein || !carbs || !fat) {
      Alert.alert("Preencha todos os campos", "Calorias, proteína, carboidrato e gordura são obrigatórios.");
      return;
    }
    setIsSubmitting(true);
    try {
      const goal = await applyManualGoal({
        kcal,
        protein_g: protein,
        carbs_g: carbs,
        fat_g: fat,
      });
      setCurrentGoal(goal);
      Alert.alert("Meta salva", "Sua meta manual foi definida.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>
        Meta de calorias
      </Text>

      {currentGoal ? (
        <View
          style={{
            backgroundColor: colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            Meta atual ({currentGoal.mode === "auto" ? "automática" : "manual"})
          </Text>
          <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.xs }]}>
            {Math.round(currentGoal.kcal)} kcal
          </Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
            P {Math.round(currentGoal.protein_g)}g · C {Math.round(currentGoal.carbs_g)}g · G{" "}
            {Math.round(currentGoal.fat_g)}g
          </Text>
        </View>
      ) : null}

      {suggestion ? (
        <View style={{ marginBottom: spacing.lg }}>
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
            Cálculo automático (Mifflin-St Jeor)
          </Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
            Baseado no seu peso, altura, idade e objetivo: {Math.round(suggestion.kcal)} kcal · P{" "}
            {Math.round(suggestion.protein_g)}g · C {Math.round(suggestion.carbs_g)}g · G{" "}
            {Math.round(suggestion.fat_g)}g
            {suggestion.changed_significantly && currentGoal
              ? ` (mudou em relação à sua meta atual)`
              : ""}
          </Text>
          <Button title="Usar cálculo automático" onPress={handleApplyAuto} loading={isSubmitting} />
        </View>
      ) : null}

      <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        Ou defina manualmente
      </Text>
      <ManualInput label="Calorias (kcal)" value={manualKcal} onChangeText={setManualKcal} />
      <ManualInput label="Proteína (g)" value={manualProtein} onChangeText={setManualProtein} />
      <ManualInput label="Carboidrato (g)" value={manualCarbs} onChangeText={setManualCarbs} />
      <ManualInput label="Gordura (g)" value={manualFat} onChangeText={setManualFat} />
      <Button title="Salvar meta manual" variant="ghost" onPress={handleApplyManual} loading={isSubmitting} />
    </ScrollView>
  );
}

function ManualInput({
  label,
  value,
  onChangeText,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ marginBottom: spacing.sm }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
        {label}
      </Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            height: 44,
            backgroundColor: colors.surface,
          },
        ]}
      />
    </View>
  );
}
