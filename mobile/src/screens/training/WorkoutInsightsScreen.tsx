import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { getWorkoutInsights, type DeloadSuggestion, type PlateauEntry } from "../../api/workoutInsights";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { useTheme } from "../../theme/ThemeProvider";

export function WorkoutInsightsScreen() {
  const { colors, type, spacing } = useTheme();
  const [plateaus, setPlateaus] = useState<PlateauEntry[]>([]);
  const [deload, setDeload] = useState<DeloadSuggestion | null>(null);

  useEffect(() => {
    getWorkoutInsights().then((data) => {
      setPlateaus(data.plateaus);
      setDeload(data.deload);
    });
  }, []);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {deload ? (
        <Card
          accent={deload.suggested ? colors.warning : colors.success}
          style={{ marginBottom: spacing.lg }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
            <Ionicons
              name={deload.suggested ? "battery-half" : "battery-full"}
              size={20}
              color={deload.suggested ? colors.warning : colors.success}
            />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8 }]}>Deload</Text>
            <HelpDot
              title="O que é deload?"
              text={
                "Uma semana mais leve de propósito (menos peso ou menos séries) depois de várias semanas intensas. " +
                "Parece contraintuitivo, mas é quando o corpo se recupera de verdade e volta a progredir. " +
                "Recomendado a cada 4-8 semanas de treino pesado."
              }
            />
            <View style={{ flex: 1 }} />
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {deload.consecutive_weeks_trained} semanas seguidas
            </Text>
          </View>
          <Text style={[type.bodySmall, { color: colors.textPrimary }]}>{deload.message}</Text>
        </Card>
      ) : null}

      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase" }]}>
          Exercícios em platô
        </Text>
        <HelpDot
          title="O que é platô?"
          text={
            "É quando um exercício para de evoluir: você repete o mesmo peso por várias sessões seguidas. " +
            "É normal e tem solução — trocar o exercício, mudar a faixa de repetições ou fazer um deload."
          }
        />
      </View>
      {plateaus.length === 0 ? (
        <Card>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="trending-up" size={24} color={colors.success} style={{ marginRight: spacing.sm }} />
            <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>
              Nenhum platô detectado — sua progressão está indo bem.
            </Text>
          </View>
        </Card>
      ) : (
        plateaus.map((p) => (
          <Card key={p.exercise_id} accent={colors.warning} style={{ marginBottom: spacing.sm }}>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{p.exercise_name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4 }]}>
              {p.sessions_without_progress} sessões paradas em {p.current_weight_kg}kg — considere trocar o
              exercício, mudar a faixa de repetições ou fazer um deload.
            </Text>
          </Card>
        ))
      )}
    </ScrollView>
  );
}
