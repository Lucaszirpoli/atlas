import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Text, TextInput, TouchableOpacity, View } from "react-native";

import {
  getNutritionHistory,
  getVolumeEvolution,
  getWeightEvolution,
} from "../../api/evolution";
import { logWeight } from "../../api/weight";
import { Card } from "../../components/Card";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useTheme } from "../../theme/ThemeProvider";

type Metric = "peso" | "calorias" | "treino";

const METRICS: { key: Metric; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "peso", label: "Peso", icon: "trending-down" },
  { key: "calorias", label: "Calorias", icon: "flame" },
  { key: "treino", label: "Treino", icon: "barbell" },
];

/** UM gráfico por vez, limpo — o oposto da tela de Evolução antiga (onde a
 * pessoa empilhava várias métricas normalizadas no mesmo plano). O Coaching
 * mostra o que importa, simples, e deixa registrar o peso ali mesmo (o motor
 * precisa desse dado). */
export function CoachingProgress({
  periodDays,
  onDataChanged,
}: {
  periodDays: number;
  onDataChanged: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [metric, setMetric] = useState<Metric>("peso");
  const [loading, setLoading] = useState(true);

  const [weight, setWeight] = useState<ChartPoint[]>([]);
  const [calories, setCalories] = useState<ChartPoint[]>([]);
  const [goalKcal, setGoalKcal] = useState<number | null>(null);
  const [volume, setVolume] = useState<ChartPoint[]>([]);

  const [novoPeso, setNovoPeso] = useState("");
  const [salvando, setSalvando] = useState(false);

  const load = useCallback(() => {
    // cutoff calculado AQUI dentro: se ficasse no corpo do componente com
    // Date.now(), mudaria a cada render, o useCallback trocaria a cada render e
    // o useEffect entraria em loop infinito ("Maximum update depth exceeded").
    const cutoff = Date.now() - periodDays * 86400000;
    setLoading(true);
    return Promise.all([
      getWeightEvolution()
        .then((pts) =>
          setWeight(pts.map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg })).filter((p) => p.x >= cutoff))
        )
        .catch(() => setWeight([])),
      getNutritionHistory(periodDays)
        .then((h) => {
          setCalories(h.days.map((d) => ({ x: new Date(d.date).getTime(), y: d.kcal })).filter((p) => p.y > 0));
          setGoalKcal(h.goal_kcal ?? null);
        })
        .catch(() => setCalories([])),
      getVolumeEvolution()
        .then((pts) =>
          setVolume(pts.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg })).filter((p) => p.x >= cutoff))
        )
        .catch(() => setVolume([])),
    ]).finally(() => setLoading(false));
  }, [periodDays]);

  useEffect(() => {
    load();
  }, [load]);

  async function salvarPeso() {
    const v = Number(novoPeso.replace(",", "."));
    if (!Number.isFinite(v) || v <= 0) return;
    setSalvando(true);
    try {
      await logWeight(v);
      setNovoPeso("");
      await load();
      onDataChanged(); // a análise depende do peso — recarrega
    } catch {
      // silencioso — a pessoa tenta de novo
    } finally {
      setSalvando(false);
    }
  }

  const active = metric === "peso" ? weight : metric === "calorias" ? calories : volume;
  const color =
    metric === "peso" ? colors.primary : metric === "calorias" ? colors.moduleNutrition : colors.moduleTraining;

  const series = [{ data: active, color, area: true, showDots: active.length <= 14 }];
  // Linha de meta tracejada só nas calorias (referência do alvo).
  if (metric === "calorias" && goalKcal && active.length > 0) {
    const xs = active.map((p) => p.x);
    series.push({
      data: [
        { x: Math.min(...xs), y: goalKcal },
        { x: Math.max(...xs), y: goalKcal },
      ],
      color: colors.textSecondary,
      dashed: true,
    } as any);
  }

  const formatY =
    metric === "treino"
      ? (v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10}k` : String(Math.round(v)))
      : (v: number) => String(Math.round(v));

  const vazio = active.length === 0;
  const legenda =
    metric === "peso"
      ? "Seu peso ao longo do período."
      : metric === "calorias"
      ? "Calorias por dia — a linha tracejada é sua meta."
      : "Volume por treino (kg levantados).";

  return (
    <>
      <Text
        style={[
          type.caption,
          { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm },
        ]}
      >
        Seu progresso
      </Text>

      {/* Seletor de métrica — UMA por vez */}
      <View style={{ flexDirection: "row", gap: spacing.xs, marginBottom: spacing.sm }}>
        {METRICS.map((m) => {
          const on = metric === m.key;
          return (
            <TouchableOpacity
              key={m.key}
              onPress={() => setMetric(m.key)}
              style={{
                flex: 1,
                flexDirection: "row",
                justifyContent: "center",
                alignItems: "center",
                gap: 5,
                backgroundColor: on ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: on ? colors.primary : colors.border,
                borderRadius: radius.pill,
                paddingVertical: 8,
              }}
            >
              <Ionicons name={m.icon} size={14} color={on ? colors.textOnPrimary : colors.textSecondary} />
              <Text
                style={[
                  type.caption,
                  { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: on ? "700" : "500" },
                ]}
              >
                {m.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <Card style={{ marginBottom: spacing.md }}>
        {loading ? (
          <View style={{ height: 200, alignItems: "center", justifyContent: "center" }}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : vazio ? (
          <View style={{ height: 200, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="analytics-outline" size={28} color={colors.textSecondary} />
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 8, textAlign: "center" }]}>
              {metric === "peso"
                ? "Registre seu peso abaixo pra começar o gráfico."
                : metric === "calorias"
                ? "Registre refeições pra ver as calorias no período."
                : "Conclua treinos pra ver seu volume evoluir."}
            </Text>
          </View>
        ) : (
          <>
            <LineChart series={series as any} height={200} formatY={formatY} />
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>{legenda}</Text>
          </>
        )}

        {/* Registrar peso ali mesmo — o coach precisa desse dado (fica só na
            métrica de peso pra não poluir). */}
        {metric === "peso" ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md }}>
            <TextInput
              value={novoPeso}
              onChangeText={(v) => setNovoPeso(v.replace(/,/g, ".").replace(/[^0-9.]/g, ""))}
              keyboardType="decimal-pad"
              placeholder="Peso de hoje (kg)"
              placeholderTextColor={colors.textSecondary}
              style={[
                type.body,
                {
                  flex: 1,
                  color: colors.textPrimary,
                  backgroundColor: colors.surfaceAlt,
                  borderRadius: radius.button,
                  height: 46,
                  paddingHorizontal: spacing.md,
                },
              ]}
            />
            <TouchableOpacity
              onPress={salvarPeso}
              disabled={salvando || !novoPeso}
              style={{
                backgroundColor: colors.primary,
                borderRadius: radius.button,
                height: 46,
                paddingHorizontal: spacing.lg,
                alignItems: "center",
                justifyContent: "center",
                opacity: salvando || !novoPeso ? 0.5 : 1,
              }}
            >
              <Text style={[type.body, { color: colors.textOnPrimary, fontWeight: "700" }]}>
                {salvando ? "..." : "Registrar"}
              </Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </Card>
    </>
  );
}
