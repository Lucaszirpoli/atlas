import { Ionicons } from "@expo/vector-icons";
import { useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import {
  getConsistency,
  getExerciseProgression,
  getExercisesWithHistory,
  getVolumeEvolution,
  getWeightEvolution,
  type ConsistencyDay,
  type ConsistencyHistory,
  type ExerciseOption,
  type ExerciseProgressionPoint,
  type VolumePoint,
  type WeightPoint,
} from "../../api/evolution";
import { logWeight } from "../../api/weight";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useTheme } from "../../theme/ThemeProvider";

function movingAverage(points: WeightPoint[], window = 7): ChartPoint[] {
  return points.map((p, i) => {
    const slice = points.slice(Math.max(0, i - window + 1), i + 1);
    const avg = slice.reduce((s, x) => s + x.weight_kg, 0) / slice.length;
    return { x: new Date(p.date).getTime(), y: avg };
  });
}

// Tudo em UMA tela só: a pessoa escolhe o que quer ver (Constância, Peso,
// Volume ou Carga) num seletor no topo e só aquele conteúdo aparece — sem
// abas escondendo informação, sem "onde é que eu acho isso mesmo".
type ViewMode = "consistency" | "weight" | "volume" | "load";

const VIEW_OPTIONS: { key: ViewMode; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "consistency", label: "Constância", icon: "flame" },
  { key: "weight", label: "Peso", icon: "scale" },
  { key: "volume", label: "Volume", icon: "stats-chart" },
  { key: "load", label: "Carga", icon: "trending-up" },
];

function viewColor(colors: ReturnType<typeof useTheme>["colors"], key: ViewMode): string {
  return {
    consistency: colors.secondary,
    weight: colors.primary,
    volume: colors.secondary,
    load: colors.moduleTraining,
  }[key];
}

export function EvolutionScreen() {
  const { colors, type, spacing } = useTheme();
  const route = useRoute<any>();
  const [viewMode, setViewMode] = useState<ViewMode>(route.params?.initialView ?? "consistency");

  const [weight, setWeight] = useState<WeightPoint[]>([]);
  const [volume, setVolume] = useState<VolumePoint[]>([]);
  const [exercises, setExercises] = useState<ExerciseOption[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<ExerciseOption | null>(null);
  const [progression, setProgression] = useState<ExerciseProgressionPoint[]>([]);
  const [newWeight, setNewWeight] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [consistency, setConsistency] = useState<ConsistencyHistory | null>(null);

  async function loadAll() {
    const [w, v, ex, c] = await Promise.all([
      getWeightEvolution(),
      getVolumeEvolution(),
      getExercisesWithHistory(),
      getConsistency(30),
    ]);
    setWeight(w);
    setVolume(v);
    setExercises(ex);
    setConsistency(c);
    if (ex.length > 0 && !selectedExercise) {
      setSelectedExercise(ex[0]);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (selectedExercise) {
      getExerciseProgression(selectedExercise.id).then((r) => setProgression(r.points));
    }
  }, [selectedExercise]);

  async function handleSaveWeight() {
    const value = Number(newWeight.replace(",", "."));
    if (!value || value < 30 || value > 400) {
      Alert.alert("Peso inválido", "Informe um valor entre 30 e 400 kg.");
      return;
    }
    setIsSaving(true);
    try {
      await logWeight(value);
      setNewWeight("");
      await loadAll();
    } finally {
      setIsSaving(false);
    }
  }

  const weightSeries: ChartPoint[] = weight.map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg }));
  const weightAvg = movingAverage(weight);
  const latestWeight = weight.length ? weight[weight.length - 1].weight_kg : null;
  const weightDelta = weight.length >= 2 ? weight[weight.length - 1].weight_kg - weight[0].weight_kg : 0;

  const volumeSeries: ChartPoint[] = volume.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg }));
  const progSeries: ChartPoint[] = progression.map((p) => ({ x: new Date(p.date).getTime(), y: p.max_weight_kg }));

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Seletor único — 4 opções, uma tela, sem abas escondendo nada */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          {VIEW_OPTIONS.map((opt) => {
            const active = viewMode === opt.key;
            const color = viewColor(colors, opt.key);
            return (
              <TouchableOpacity
                key={opt.key}
                onPress={() => setViewMode(opt.key)}
                activeOpacity={0.85}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 7,
                  paddingVertical: 10,
                  paddingHorizontal: 16,
                  borderRadius: 999,
                  backgroundColor: active ? color : colors.surface,
                  borderWidth: 1,
                  borderColor: active ? color : colors.border,
                }}
              >
                <Ionicons name={opt.icon} size={18} color={active ? colors.textOnPrimary : colors.textSecondary} />
                <Text
                  style={[
                    type.caption,
                    { color: active ? colors.textOnPrimary : colors.textPrimary, fontWeight: "700" },
                  ]}
                >
                  {opt.key === "consistency" && consistency?.current_streak
                    ? `${opt.label} · ${consistency.current_streak}d 🔥`
                    : opt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {viewMode === "consistency" ? <ConsistencyCard /> : null}

      {viewMode === "weight" ? (
        <Card accent={colors.primary}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
            <Ionicons name="scale" size={18} color={colors.primary} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1 }]}>Peso</Text>
            <HelpDot
              title="Média móvel de 7 dias"
              text={
                "O peso oscila muito de um dia pro outro (água, comida, intestino). A linha tracejada é a média " +
                "dos últimos 7 dias — ela mostra a tendência real, sem o sobe-e-desce que costuma dar ansiedade."
              }
            />
          </View>
          {latestWeight ? (
            <View style={{ flexDirection: "row", alignItems: "baseline", marginBottom: spacing.sm }}>
              <Text style={[type.display, { color: colors.textPrimary, fontSize: 34 }]}>{latestWeight}</Text>
              <Text style={[type.h2, { color: colors.textSecondary }]}> kg</Text>
              {weight.length >= 2 ? (
                <Text
                  style={[
                    type.bodySmall,
                    { color: weightDelta <= 0 ? colors.success : colors.warning, marginLeft: spacing.sm, fontWeight: "700" },
                  ]}
                >
                  {weightDelta > 0 ? "+" : ""}
                  {weightDelta.toFixed(1)}kg no período
                </Text>
              ) : null}
            </View>
          ) : null}

          {weight.length >= 2 ? (
            <LineChart
              series={[
                { data: weightSeries, color: colors.primary, showDots: true, area: true },
                { data: weightAvg, color: colors.primary, dashed: true },
              ]}
              formatY={(v) => v.toFixed(1)}
              showMinMax
            />
          ) : (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginVertical: spacing.sm }]}>
              Registre seu peso ao menos 2 vezes para ver o gráfico de tendência.
            </Text>
          )}

          <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm, alignItems: "center" }}>
            <TextInput
              value={newWeight}
              onChangeText={(v) => setNewWeight(v.replace(/[^0-9.,]/g, ""))}
              keyboardType="decimal-pad"
              placeholder="Novo peso (kg)"
              placeholderTextColor={colors.textSecondary}
              style={[
                type.body,
                {
                  flex: 1,
                  color: colors.textPrimary,
                  backgroundColor: colors.surfaceAlt,
                  borderRadius: 14,
                  height: 48,
                  paddingHorizontal: spacing.md,
                  textAlign: "center",
                },
              ]}
            />
            <Button title="Registrar" onPress={handleSaveWeight} loading={isSaving} />
          </View>
        </Card>
      ) : null}

      {viewMode === "volume" ? (
        <Card accent={colors.secondary}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Ionicons name="stats-chart" size={18} color={colors.secondary} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1 }]}>Volume de treino</Text>
            <HelpDot
              title="Volume total"
              text={
                "Volume = peso × repetições, somado de todas as séries de um treino. É um bom indicador de quanto " +
                "trabalho você fez. Subir o volume ao longo das semanas costuma andar junto com ganho de força e músculo."
              }
            />
          </View>
          {volume.length >= 2 ? (
            <LineChart
              series={[{ data: volumeSeries, color: colors.secondary, showDots: true, area: true }]}
              formatY={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}t` : `${Math.round(v)}`)}
              showMinMax
            />
          ) : (
            <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
              Conclua ao menos 2 treinos para ver a evolução do volume.
            </Text>
          )}
        </Card>
      ) : null}

      {viewMode === "load" ? (
        <Card accent={colors.moduleTraining}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Ionicons name="trending-up" size={18} color={colors.moduleTraining} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8 }]}>Carga por exercício</Text>
          </View>
          {exercises.length === 0 ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
              Registre treinos para acompanhar a evolução de carga de cada exercício.
            </Text>
          ) : (
            <>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.sm }}>
                <View style={{ flexDirection: "row", gap: spacing.xs }}>
                  {exercises.map((ex) => {
                    const active = selectedExercise?.id === ex.id;
                    return (
                      <TouchableOpacity
                        key={ex.id}
                        onPress={() => setSelectedExercise(ex)}
                        style={{
                          borderRadius: 999,
                          paddingVertical: 8,
                          paddingHorizontal: 14,
                          backgroundColor: active ? colors.moduleTraining : colors.surfaceAlt,
                        }}
                      >
                        <Text
                          style={[
                            type.caption,
                            { color: active ? colors.textOnPrimary : colors.textPrimary, fontWeight: active ? "700" : "500" },
                          ]}
                        >
                          {ex.name}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </ScrollView>
              {progSeries.length >= 2 ? (
                <LineChart
                  series={[{ data: progSeries, color: colors.moduleTraining, showDots: true, area: true }]}
                  formatY={(v) => `${Math.round(v)}kg`}
                  showMinMax
                />
              ) : (
                <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
                  Faça esse exercício em ao menos 2 treinos para ver o gráfico.
                </Text>
              )}
            </>
          )}
        </Card>
      ) : null}
    </ScrollView>
  );
}

// --- Constância ------------------------------------------------------------
// Mede o quanto a pessoa tem sido consistente nos 4 hábitos que o app
// acompanha (treino, sono bom, água na meta, dieta registrada) e deixa
// filtrar o gráfico pra ver só um deles — sem julgamento, um dia sem
// registro é só isso, nunca "falha" (espec. 3.7).

type ConsistencyFilterKey = "geral" | "treino" | "sono" | "agua" | "dieta";

const CONSISTENCY_FILTERS: { key: ConsistencyFilterKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "geral", label: "Geral", icon: "flame" },
  { key: "treino", label: "Treino", icon: "barbell" },
  { key: "sono", label: "Sono", icon: "moon" },
  { key: "agua", label: "Água", icon: "water" },
  { key: "dieta", label: "Dieta", icon: "restaurant" },
];

function useConsistencyFilterColor(filter: ConsistencyFilterKey): string {
  const { colors } = useTheme();
  return {
    geral: colors.secondary,
    treino: colors.moduleTraining,
    sono: colors.moduleSleep,
    agua: colors.info,
    dieta: colors.moduleNutrition,
  }[filter];
}

function ConsistencyCard() {
  const { colors, type, spacing } = useTheme();
  const [history, setHistory] = useState<ConsistencyHistory | null>(null);
  const [filter, setFilter] = useState<ConsistencyFilterKey>("geral");
  const filterColor = useConsistencyFilterColor(filter);

  useEffect(() => {
    getConsistency(30).then(setHistory).catch(() => {});
  }, []);

  return (
    <Card accent={filterColor}>
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
        <Ionicons name="flame" size={18} color={colors.secondary} />
        <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1 }]}>Média da constância</Text>
        <HelpDot
          title="Como isso é calculado"
          text={
            "Todo dia contamos 4 hábitos: treinar, dormir bem (7h ou mais), beber sua meta de água e registrar o " +
            "que comeu. Bateu pelo menos 2 dos 4? O dia entra na sua sequência. Não é sobre ser perfeito todo dia — " +
            "é sobre aparecer com frequência."
          }
        />
      </View>

      {history ? (
        <>
          <View style={{ flexDirection: "row", alignItems: "baseline", marginBottom: spacing.md }}>
            <Text style={[type.display, { color: colors.textPrimary, fontSize: 34 }]}>{history.current_streak}</Text>
            <Text style={[type.body, { color: colors.textSecondary, marginLeft: 6 }]}>
              {history.current_streak === 1 ? "dia seguido" : "dias seguidos"} 🔥
            </Text>
            {history.best_streak > history.current_streak ? (
              <Text style={[type.caption, { color: colors.textSecondary, marginLeft: "auto" }]}>
                recorde: {history.best_streak}
              </Text>
            ) : null}
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.sm }}>
            <View style={{ flexDirection: "row", gap: spacing.xs }}>
              {CONSISTENCY_FILTERS.map((f) => {
                const active = filter === f.key;
                return (
                  <ConsistencyFilterChip
                    key={f.key}
                    filter={f}
                    active={active}
                    onPress={() => setFilter(f.key)}
                  />
                );
              })}
            </View>
          </ScrollView>

          <ConsistencyBars days={history.days} filter={filter} color={filterColor} />
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 4 }}>
            <Text style={[type.caption, { color: colors.textSecondary }]}>30 dias atrás</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>hoje</Text>
          </View>
        </>
      ) : (
        <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
          Carregando sua constância...
        </Text>
      )}
    </Card>
  );
}

function ConsistencyFilterChip({
  filter,
  active,
  onPress,
}: {
  filter: (typeof CONSISTENCY_FILTERS)[number];
  active: boolean;
  onPress: () => void;
}) {
  const { colors, type } = useTheme();
  const color = useConsistencyFilterColor(filter.key);
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 7,
        borderRadius: 999,
        paddingVertical: 10,
        paddingHorizontal: 16,
        backgroundColor: active ? color : colors.surfaceAlt,
      }}
    >
      <Ionicons name={filter.icon} size={18} color={active ? colors.textOnPrimary : colors.textSecondary} />
      <Text
        style={[
          type.caption,
          { color: active ? colors.textOnPrimary : colors.textPrimary, fontWeight: active ? "700" : "500", fontSize: 13 },
        ]}
      >
        {filter.label}
      </Text>
    </TouchableOpacity>
  );
}

function ConsistencyBars({
  days,
  filter,
  color,
}: {
  days: ConsistencyDay[];
  filter: ConsistencyFilterKey;
  color: string;
}) {
  const { colors } = useTheme();
  const CHART_H = 90;

  function valueOf(d: ConsistencyDay): number {
    switch (filter) {
      case "geral":
        return d.score / 100;
      case "treino":
        return d.trained ? 1 : 0;
      case "sono":
        return d.slept_well ? 1 : 0;
      case "agua":
        return d.hydrated ? 1 : 0;
      case "dieta":
        return d.logged_food ? 1 : 0;
    }
  }

  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", height: CHART_H, gap: 3 }}>
      {days.map((d) => {
        const v = valueOf(d);
        const h = v > 0 ? Math.max(v * CHART_H, 4) : 2;
        return (
          <View
            key={d.date}
            style={{
              flex: 1,
              height: h,
              borderRadius: 3,
              backgroundColor: v > 0 ? color : colors.surfaceAlt,
              opacity: v > 0 ? 0.35 + v * 0.65 : 1,
            }}
          />
        );
      })}
    </View>
  );
}
