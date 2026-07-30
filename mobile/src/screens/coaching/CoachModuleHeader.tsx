import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Text, View } from "react-native";

import { getCoachingAnalysis, type CoachingAnalysis } from "../../api/coaching";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

/** Etiqueta "SEU COACHING" que abre cada bloco de coach nas telas de módulo. */
function CoachLabel() {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm }}>
      <Ionicons name="compass-outline" size={15} color={colors.primary} />
      <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.6, textTransform: "uppercase" }]}>
        Seu coaching
      </Text>
    </View>
  );
}

/** Hook: só o Pro tem coach. Carrega a análise a cada foco. */
function useCoachAnalysis() {
  const { user } = useAuth();
  const isPro = user?.plan === "pro";
  const [analysis, setAnalysis] = useState<CoachingAnalysis | null>(null);

  const reload = useCallback(() => {
    if (!isPro) return;
    getCoachingAnalysis()
      .then(setAnalysis)
      .catch(() => {});
  }, [isPro]);

  useFocusEffect(
    useCallback(() => {
      reload();
    }, [reload])
  );

  return { isPro, analysis, reload };
}

/** Leitura curta do coach sobre uma métrica (peso/sono) — no topo da tela do
 * módulo. Some pro Free. */
function MetricCoachReading({ metricKey, fallback }: { metricKey: string; fallback: string }) {
  const { colors, type, spacing } = useTheme();
  const { isPro, analysis } = useCoachAnalysis();
  if (!isPro || !analysis) return null;
  const ins = analysis.insights.find((i) => i.key === metricKey);
  return (
    <View style={{ marginBottom: spacing.sm }}>
      <CoachLabel />
      <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", marginBottom: 3 }]}>
          {ins?.title ?? "Leitura do coach"}
        </Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 20 }]}>
          {ins?.detail ?? fallback}
        </Text>
      </Card>
    </View>
  );
}

/** Cabeçalho do coach na tela de PESO (Pro). */
export function WeightCoachHeader() {
  return <MetricCoachReading metricKey="peso" fallback="Registre seu peso que eu acompanho a tendência ao longo das semanas." />;
}

/** Cabeçalho do coach na tela de SONO (Pro). */
export function SleepCoachHeader() {
  return <MetricCoachReading metricKey="sono" fallback="Registre suas noites que eu cruzo o sono com o seu treino e recuperação." />;
}
