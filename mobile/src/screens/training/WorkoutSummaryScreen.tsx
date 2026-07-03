import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React from "react";
import { ScrollView, Text, View } from "react-native";

import type { WorkoutSessionSummary } from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Confetti } from "../../components/Confetti";
import { useTheme } from "../../theme/ThemeProvider";

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}min ${seconds}s`;
}

export function WorkoutSummaryScreen() {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { summary }: { summary: WorkoutSessionSummary } = route.params;

  const uniqueExercises = new Set(summary.session.sets.map((s) => s.exercise_id)).size;
  const hasPr = summary.prs.length > 0;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {hasPr ? <Confetti /> : null}
      {/* Celebração */}
      <View style={{ alignItems: "center", marginVertical: spacing.lg }}>
        <View
          style={[
            {
              width: 84,
              height: 84,
              borderRadius: 28,
              backgroundColor: colors.secondary,
              alignItems: "center",
              justifyContent: "center",
              marginBottom: spacing.md,
            },
            shadow.md,
          ]}
        >
          <Ionicons name="checkmark-done" size={44} color={colors.textOnPrimary} />
        </View>
        <Text style={[type.h1, { color: colors.textPrimary }]}>Treino concluído!</Text>
        <Text style={[type.display, { color: colors.secondary, fontSize: 48, lineHeight: 56, marginTop: spacing.xs }]}>
          {Math.round(summary.total_volume_kg)}
          <Text style={[type.h2, { color: colors.textSecondary }]}> kg</Text>
        </Text>
        <Text style={[type.caption, { color: colors.textSecondary }]}>volume total levantado</Text>
      </View>

      {/* PRs */}
      {summary.prs.length > 0 ? (
        <Card accent={colors.secondary} style={{ marginBottom: spacing.md, backgroundColor: colors.secondarySoft }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
            <Text style={{ fontSize: 22, marginRight: 8 }}>🏆</Text>
            <Text style={[type.h2, { color: colors.secondary }]}>Novo recorde pessoal!</Text>
          </View>
          {summary.prs.map((pr) => (
            <Text key={pr.exercise_id} style={[type.body, { color: colors.textPrimary, marginTop: 2 }]}>
              {pr.exercise_name}: <Text style={{ fontWeight: "800" }}>{pr.weight_kg}kg</Text>
            </Text>
          ))}
        </Card>
      ) : null}

      {/* Stats */}
      <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
        <StatBox icon="time" label="Duração" value={formatDuration(summary.duration_seconds)} />
        <StatBox icon="barbell" label="Exercícios" value={String(uniqueExercises)} />
        <StatBox icon="repeat" label="Séries" value={String(summary.session.sets.length)} />
      </View>

      {/* Comparação */}
      <Card style={{ marginBottom: spacing.lg }}>
        {summary.volume_change_percent !== null ? (
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons
              name={summary.volume_change_percent >= 0 ? "trending-up" : "trending-down"}
              size={26}
              color={summary.volume_change_percent >= 0 ? colors.success : colors.textSecondary}
              style={{ marginRight: spacing.sm }}
            />
            <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]}>
              Você levantou{" "}
              <Text style={{ fontWeight: "800", color: summary.volume_change_percent >= 0 ? colors.success : colors.textPrimary }}>
                {Math.abs(summary.volume_change_percent)}% {summary.volume_change_percent >= 0 ? "mais" : "menos"}
              </Text>{" "}
              volume que da última vez nessa rotina.
            </Text>
          </View>
        ) : (
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="sparkles" size={24} color={colors.primary} style={{ marginRight: spacing.sm }} />
            <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]}>
              Primeira vez nessa rotina — esse é seu ponto de partida.
            </Text>
          </View>
        )}
      </Card>

      <Button title="Voltar para rotinas" onPress={() => navigation.popToTop()} />
    </ScrollView>
  );
}

function StatBox({ icon, label, value }: { icon: keyof typeof Ionicons.glyphMap; label: string; value: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <Card style={{ flex: 1, alignItems: "center", paddingVertical: spacing.md }}>
      <Ionicons name={icon} size={20} color={colors.secondary} />
      <Text style={[type.h2, { color: colors.textPrimary, marginTop: 6, fontSize: 17 }]}>{value}</Text>
      <Text style={[type.caption, { color: colors.textSecondary }]}>{label}</Text>
    </Card>
  );
}
