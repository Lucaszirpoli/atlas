import { useNavigation, useRoute } from "@react-navigation/native";
import React from "react";
import { ScrollView, Text, View } from "react-native";

import type { WorkoutSessionSummary } from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { useTheme } from "../../theme/ThemeProvider";

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}min ${seconds}s`;
}

export function WorkoutSummaryScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { summary }: { summary: WorkoutSessionSummary } = route.params;

  const uniqueExercises = new Set(summary.session.sets.map((s) => s.exercise_id)).size;

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.lg }]}>
        Treino concluído
      </Text>

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
        <SummaryRow label="Volume total" value={`${Math.round(summary.total_volume_kg)} kg`} />
        <SummaryRow label="Duração" value={formatDuration(summary.duration_seconds)} />
        <SummaryRow label="Exercícios" value={String(uniqueExercises)} />
        <SummaryRow label="Séries" value={String(summary.session.sets.length)} />
      </View>

      {summary.volume_change_percent !== null ? (
        <Text style={[type.body, { color: colors.textPrimary, marginBottom: spacing.lg }]}>
          Você levantou {Math.abs(summary.volume_change_percent)}%{" "}
          {summary.volume_change_percent >= 0 ? "mais" : "menos"} volume que da última vez nessa
          rotina.
        </Text>
      ) : (
        <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
          Essa foi a primeira vez que você concluiu essa rotina.
        </Text>
      )}

      <Button title="Voltar para rotinas" onPress={() => navigation.popToTop()} />
    </ScrollView>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.xs }}>
      <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{label}</Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary }]}>{value}</Text>
    </View>
  );
}
