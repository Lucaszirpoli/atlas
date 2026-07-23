import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Text, TextInput, TouchableOpacity, View } from "react-native";

import type { CoachingChart } from "../../api/coaching";
import { getNutritionHistory, getVolumeEvolution, getWeightEvolution } from "../../api/evolution";
import { listSleepLogs } from "../../api/sleep";
import { logWeight } from "../../api/weight";
import { Card } from "../../components/Card";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useTheme } from "../../theme/ThemeProvider";

const METRICS: { key: CoachingChart; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "peso", label: "Peso", icon: "trending-down" },
  { key: "calorias", label: "Calorias", icon: "flame" },
  { key: "macros", label: "Macros", icon: "restaurant" },
  { key: "sono", label: "Sono", icon: "moon" },
  { key: "carga", label: "Carga", icon: "barbell" },
];

/** UM gráfico por vez, limpo — o oposto da tela de Evolução antiga (mistura de
 * métricas normalizadas). Controlado: a métrica vem de fora (as barras têm um
 * quadradinho que troca o gráfico). Deixa registrar o peso ali mesmo. */
export function CoachingProgress({
  periodDays,
  metric,
  onMetricChange,
  onDataChanged,
}: {
  periodDays: number;
  metric: CoachingChart;
  onMetricChange: (m: CoachingChart) => void;
  onDataChanged: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [loading, setLoading] = useState(true);

  const [weight, setWeight] = useState<ChartPoint[]>([]);
  const [calories, setCalories] = useState<ChartPoint[]>([]);
  const [goalKcal, setGoalKcal] = useState<number | null>(null);
  const [macros, setMacros] = useState<{ prot: ChartPoint[]; carb: ChartPoint[]; fat: ChartPoint[] }>({
    prot: [],
    carb: [],
    fat: [],
  });
  const [sono, setSono] = useState<ChartPoint[]>([]);
  const [carga, setCarga] = useState<ChartPoint[]>([]);

  const [novoPeso, setNovoPeso] = useState("");
  const [salvando, setSalvando] = useState(false);

  const load = useCallback(() => {
    // cutoff calculado AQUI dentro (Date.now() no corpo entraria nas deps e
    // causaria loop de render).
    const cutoff = Date.now() - periodDays * 86400000;
    const inWin = (p: ChartPoint) => p.x >= cutoff;
    setLoading(true);
    return Promise.all([
      getWeightEvolution()
        .then((pts) => setWeight(pts.map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg })).filter(inWin)))
        .catch(() => setWeight([])),
      getNutritionHistory(periodDays)
        .then((h) => {
          const dia = (d: any, y: number) => ({ x: new Date(d.date).getTime(), y });
          setCalories(h.days.filter((d) => d.kcal > 0).map((d) => dia(d, d.kcal)));
          setMacros({
            prot: h.days.filter((d) => d.kcal > 0).map((d) => dia(d, d.protein_g)),
            carb: h.days.filter((d) => d.kcal > 0).map((d) => dia(d, d.carbs_g)),
            fat: h.days.filter((d) => d.kcal > 0).map((d) => dia(d, d.fat_g)),
          });
          setGoalKcal(h.goal_kcal ?? null);
        })
        .catch(() => setCalories([])),
      getVolumeEvolution()
        .then((pts) => setCarga(pts.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg })).filter(inWin)))
        .catch(() => setCarga([])),
      listSleepLogs()
        .then((logs) =>
          setSono(
            logs
              .map((l) => ({
                x: new Date(l.sleep_at).getTime(),
                y: (new Date(l.wake_at).getTime() - new Date(l.sleep_at).getTime()) / 3600000,
              }))
              .filter((p) => p.y > 0 && p.y < 24 && inWin(p))
          )
        )
        .catch(() => setSono([])),
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
      onDataChanged();
    } catch {
      /* silencioso */
    } finally {
      setSalvando(false);
    }
  }

  // Série(s) + config por métrica.
  const cfg = buildSeries(metric, { weight, calories, goalKcal, macros, sono, carga }, colors);
  const vazio = cfg.series.every((s: any) => s.data.length === 0);

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

      {/* Seletor de métrica (rola horizontal — são 5). */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.sm }}>
        {METRICS.map((mt) => {
          const on = metric === mt.key;
          return (
            <TouchableOpacity
              key={mt.key}
              onPress={() => onMetricChange(mt.key)}
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 5,
                backgroundColor: on ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: on ? colors.primary : colors.border,
                borderRadius: radius.pill,
                paddingVertical: 7,
                paddingHorizontal: 12,
              }}
            >
              <Ionicons name={mt.icon} size={13} color={on ? colors.textOnPrimary : colors.textSecondary} />
              <Text
                style={[
                  type.caption,
                  { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: on ? "700" : "500" },
                ]}
              >
                {mt.label}
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
              {cfg.empty}
            </Text>
          </View>
        ) : (
          <>
            <LineChart series={cfg.series as any} height={200} formatY={cfg.formatY} />
            {cfg.legend ? (
              <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.sm }}>
                {cfg.legend.map((l) => (
                  <View key={l.label} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                    <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: l.color }} />
                    <Text style={[type.caption, { color: colors.textSecondary }]}>{l.label}</Text>
                  </View>
                ))}
              </View>
            ) : (
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>{cfg.legendText}</Text>
            )}
          </>
        )}

        {/* Registrar peso ali mesmo — o coach precisa desse dado. */}
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

type Data = {
  weight: ChartPoint[];
  calories: ChartPoint[];
  goalKcal: number | null;
  macros: { prot: ChartPoint[]; carb: ChartPoint[]; fat: ChartPoint[] };
  sono: ChartPoint[];
  carga: ChartPoint[];
};

function buildSeries(metric: CoachingChart, d: Data, colors: any) {
  const roundY = (v: number) => String(Math.round(v));
  if (metric === "peso") {
    return {
      series: [{ data: d.weight, color: colors.primary, area: true, showDots: d.weight.length <= 14 }],
      formatY: roundY,
      empty: "Registre seu peso abaixo pra começar o gráfico.",
      legendText: "Seu peso ao longo do período.",
      legend: null as { label: string; color: string }[] | null,
    };
  }
  if (metric === "calorias") {
    const series: any[] = [{ data: d.calories, color: colors.moduleNutrition, area: true, showDots: d.calories.length <= 14 }];
    if (d.goalKcal && d.calories.length) {
      const xs = d.calories.map((p) => p.x);
      series.push({ data: [{ x: Math.min(...xs), y: d.goalKcal }, { x: Math.max(...xs), y: d.goalKcal }], color: colors.textSecondary, dashed: true });
    }
    return { series, formatY: roundY, empty: "Registre refeições pra ver as calorias.", legendText: "Calorias por dia — a linha tracejada é sua meta.", legend: null };
  }
  if (metric === "macros") {
    return {
      series: [
        { data: d.macros.prot, color: colors.moduleTraining, showDots: false },
        { data: d.macros.carb, color: colors.info, showDots: false },
        { data: d.macros.fat, color: colors.warning, showDots: false },
      ],
      formatY: roundY,
      empty: "Registre refeições pra ver proteína, carbo e gordura.",
      legendText: "",
      legend: [
        { label: "Proteína", color: colors.moduleTraining },
        { label: "Carbo", color: colors.info },
        { label: "Gordura", color: colors.warning },
      ],
    };
  }
  if (metric === "sono") {
    return {
      series: [{ data: d.sono, color: colors.secondary, area: true, showDots: d.sono.length <= 14 }],
      formatY: (v: number) => `${Math.round(v)}h`,
      empty: "Registre o sono pra ver a evolução.",
      legendText: "Horas de sono por noite no período.",
      legend: null,
    };
  }
  // carga
  return {
    series: [{ data: d.carga, color: colors.moduleTraining, area: true, showDots: d.carga.length <= 14 }],
    formatY: (v: number) => (v >= 1000 ? `${Math.round(v / 100) / 10}k` : String(Math.round(v))),
    empty: "Conclua treinos pra ver sua carga (volume) evoluir.",
    legendText: "Volume por treino (peso × reps).",
    legend: null,
  };
}
