import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Text, TouchableOpacity, View } from "react-native";

import { getCoachingAnalysis, type CoachingAnalysis } from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { MacroChip, TrainingPrefsCard } from "./coachBlocks";

/** Etiqueta "SEU COACHING" que abre cada bloco de coach nas telas de módulo. */
function CoachLabel() {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm }}>
      <Ionicons name="compass" size={15} color={colors.primary} />
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

/** Cabeçalho do coach na tela de TREINO (Pro): "como eu monto seu treino" +
 * "seu treino". Some pro Free. */
export function TrainingCoachHeader() {
  const { spacing } = useTheme();
  const { isPro, analysis, reload } = useCoachAnalysis();
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);

  if (!isPro || !analysis) return null;

  const onApplied = (title: string, message: string) => {
    setAviso({ title, message });
    reload();
  };

  return (
    <View style={{ marginBottom: spacing.sm }}>
      <CoachLabel />
      {analysis.metrics.training_prefs ? (
        <TrainingPrefsCard
          prefs={analysis.metrics.training_prefs}
          workout={analysis.metrics.workout}
          onChanged={onApplied}
        />
      ) : null}
      <InfoDialog visible={aviso != null} onClose={() => setAviso(null)} title={aviso?.title ?? ""} message={aviso?.message} />
    </View>
  );
}

/** Cabeçalho do coach na tela de DIETA (Pro): meta calórica + macros + leitura.
 * Recolhido por padrão, com setinha pra expandir — mesmo padrão do card "Como
 * eu monto seu treino". Some pro Free. */
export function DietCoachHeader() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const { isPro, analysis } = useCoachAnalysis();
  const [expanded, setExpanded] = useState(false);

  if (!isPro || !analysis) return null;

  const m = analysis.metrics;
  const resumo = m.goal_kcal
    ? `${Math.round(m.goal_kcal)} kcal/dia · P ${Math.round(m.protein_target_g ?? 0)}g · C ${Math.round(m.goal_carbs_g ?? 0)}g · G ${Math.round(m.goal_fat_g ?? 0)}g`
    : "Você ainda não tem meta calórica — toque pra definir.";

  return (
    <View style={{ marginBottom: spacing.sm }}>
      <CoachLabel />
      <Card style={{ marginBottom: spacing.md }}>
        <TouchableOpacity
          onPress={() => setExpanded((v) => !v)}
          activeOpacity={0.7}
          style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
        >
          <Ionicons name="flag" size={16} color={colors.primary} />
          <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", flex: 1 }]}>
            Sua meta atual
          </Text>
          <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
        </TouchableOpacity>

        {expanded ? (
          <View style={{ marginTop: spacing.sm }}>
            {m.goal_kcal ? (
              <>
                <View style={{ flexDirection: "row", alignItems: "baseline", gap: 5, marginBottom: spacing.sm }}>
                  <Text style={[type.display, { color: colors.textPrimary, fontSize: 30 }]}>{Math.round(m.goal_kcal)}</Text>
                  <Text style={[type.body, { color: colors.textSecondary }]}>kcal / dia</Text>
                </View>
                <View style={{ flexDirection: "row", gap: spacing.md }}>
                  <MacroChip label="Proteína" goal={m.protein_target_g} avg={m.avg_protein_g} color={colors.moduleTraining} />
                  <MacroChip label="Carbo" goal={m.goal_carbs_g} avg={m.avg_carbs_g} color={colors.info} />
                  <MacroChip label="Gordura" goal={m.goal_fat_g} avg={m.avg_fat_g} color={colors.warning} />
                </View>
                {m.avg_kcal != null ? (
                  <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
                    Média recente: {Math.round(m.avg_kcal)} kcal/dia.
                  </Text>
                ) : null}
              </>
            ) : (
              <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                Você ainda não tem meta calórica. Defina uma pra o coach acompanhar sua dieta.
              </Text>
            )}
            {analysis.headline ? (
              <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 8, marginTop: spacing.sm }}>
                <Ionicons name="chatbubble-ellipses" size={15} color={colors.textSecondary} style={{ marginTop: 2 }} />
                <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1, lineHeight: 20 }]}>{analysis.headline}</Text>
              </View>
            ) : null}
            <View style={{ marginTop: spacing.md }}>
              <Button
                title="Ajustar meta calórica"
                variant="secondary"
                compact
                onPress={() => navigation.navigate("GoalSettings")}
              />
            </View>
          </View>
        ) : (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]} numberOfLines={2}>
            {resumo}
          </Text>
        )}
      </Card>
    </View>
  );
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
