import { Ionicons } from "@expo/vector-icons";
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
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
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
      setCurrentGoal(await applyAutoGoal());
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
      setCurrentGoal(await applyManualGoal({ kcal, protein_g: protein, carbs_g: carbs, fat_g: fat }));
      Alert.alert("Meta salva", "Sua meta manual foi definida.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {currentGoal ? (
        <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Ionicons name="flag" size={18} color={colors.primary} />
            <Text style={[type.caption, { color: colors.textSecondary, marginLeft: 6 }]}>
              META ATUAL · {currentGoal.mode === "auto" ? "AUTOMÁTICA" : "MANUAL"}
            </Text>
          </View>
          <Text style={[type.display, { color: colors.textPrimary, fontSize: 40, lineHeight: 46 }]}>
            {Math.round(currentGoal.kcal)}
            <Text style={[type.h2, { color: colors.textSecondary }]}> kcal/dia</Text>
          </Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm }}>
            <MacroChip label="P" value={currentGoal.protein_g} color={colors.moduleTraining} />
            <MacroChip label="C" value={currentGoal.carbs_g} color={colors.info} />
            <MacroChip label="G" value={currentGoal.fat_g} color={colors.warning} />
            <HelpDot
              title="Macros (P, C, G)"
              text={
                "P = proteína (constrói e mantém músculo), C = carboidrato (principal fonte de energia), " +
                "G = gordura (hormônios e saúde geral). A meta em gramas por dia de cada um compõe suas calorias totais."
              }
            />
          </View>
        </Card>
      ) : null}

      {suggestion ? (
        <Card style={{ marginBottom: spacing.lg }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
            <Ionicons name="calculator" size={18} color={colors.primary} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8 }]}>Cálculo automático</Text>
            <HelpDot
              title="Como é calculado?"
              text={
                "Usamos a fórmula Mifflin-St Jeor, a mais precisa reconhecida hoje: ela estima quanto seu corpo " +
                "gasta em repouso a partir de peso, altura, idade e sexo. Depois multiplicamos pelo seu nível de " +
                "atividade e ajustamos pro seu objetivo (déficit pra emagrecer, superávit pra ganhar massa)."
              }
            />
          </View>
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
            Pela fórmula Mifflin-St Jeor, com seu peso, altura, idade e objetivo:{" "}
            <Text style={{ color: colors.textPrimary, fontWeight: "700" }}>
              {Math.round(suggestion.kcal)} kcal
            </Text>{" "}
            · P {Math.round(suggestion.protein_g)}g · C {Math.round(suggestion.carbs_g)}g · G{" "}
            {Math.round(suggestion.fat_g)}g
            {suggestion.changed_significantly && currentGoal ? " (mudou em relação à meta atual)" : ""}
          </Text>
          <Button title="Usar cálculo automático" onPress={handleApplyAuto} loading={isSubmitting} />
        </Card>
      ) : null}

      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Ou defina manualmente
      </Text>
      <Card>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <ManualInput label="kcal" value={manualKcal} onChangeText={setManualKcal} flex={1.2} />
          <ManualInput label="Prot (g)" value={manualProtein} onChangeText={setManualProtein} />
          <ManualInput label="Carb (g)" value={manualCarbs} onChangeText={setManualCarbs} />
          <ManualInput label="Gord (g)" value={manualFat} onChangeText={setManualFat} />
        </View>
        <View style={{ marginTop: spacing.md }}>
          <Button title="Salvar meta manual" variant="ghost" onPress={handleApplyManual} loading={isSubmitting} />
        </View>
      </Card>
    </ScrollView>
  );
}

function MacroChip({ label, value, color }: { label: string; value: number; color: string }) {
  const { type, radius } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: color + "1A",
        borderRadius: radius.pill,
        paddingVertical: 4,
        paddingHorizontal: 12,
        gap: 4,
      }}
    >
      <Text style={[type.caption, { color, fontWeight: "800" }]}>{label}</Text>
      <Text style={[type.caption, { color, fontWeight: "600" }]}>{Math.round(value)}g</Text>
    </View>
  );
}

function ManualInput({
  label,
  value,
  onChangeText,
  flex = 1,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  flex?: number;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flex }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderRadius: radius.button,
            paddingHorizontal: spacing.sm,
            height: 48,
            backgroundColor: colors.surfaceAlt,
            textAlign: "center",
            fontWeight: "600",
          },
        ]}
      />
    </View>
  );
}
