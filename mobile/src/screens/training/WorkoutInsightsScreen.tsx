import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { getWorkoutInsights, type DeloadSuggestion, type PlateauEntry } from "../../api/workoutInsights";
import { useTheme } from "../../theme/ThemeProvider";

export function WorkoutInsightsScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const [plateaus, setPlateaus] = useState<PlateauEntry[]>([]);
  const [deload, setDeload] = useState<DeloadSuggestion | null>(null);

  useEffect(() => {
    getWorkoutInsights().then((data) => {
      setPlateaus(data.plateaus);
      setDeload(data.deload);
    });
  }, []);

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>
        Reavaliação do treino
      </Text>

      {deload ? (
        <View
          style={{
            backgroundColor: deload.suggested ? colors.warning + "1A" : colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: deload.suggested ? colors.warning : colors.border,
            padding: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>Deload</Text>
          <Text style={[type.bodySmall, { color: colors.textPrimary }]}>{deload.message}</Text>
        </View>
      ) : null}

      <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        Exercícios em platô
      </Text>
      {plateaus.length === 0 ? (
        <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
          Nenhum platô detectado — sua progressão está indo bem.
        </Text>
      ) : (
        plateaus.map((p) => (
          <View
            key={p.exercise_id}
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: colors.border,
              padding: spacing.md,
              marginBottom: spacing.sm,
            }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{p.exercise_name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {p.sessions_without_progress} sessões sem evoluir de {p.current_weight_kg}kg — considere
              trocar o exercício, mudar a faixa de repetições ou dar um deload.
            </Text>
          </View>
        ))
      )}
    </ScrollView>
  );
}
