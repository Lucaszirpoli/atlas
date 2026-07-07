import { Ionicons } from "@expo/vector-icons";
import { useRoute } from "@react-navigation/native";
import React, { useEffect, useMemo, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import {
  getExerciseProgression,
  getExercisesWithHistory,
  getNutritionHistory,
  getVolumeEvolution,
  getWeightEvolution,
  type ExerciseOption,
  type ExerciseProgressionPoint,
  type NutritionDay,
  type VolumePoint,
  type WeightPoint,
} from "../../api/evolution";
import { listSleepLogs, type SleepLog } from "../../api/sleep";
import { logWeight } from "../../api/weight";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useTheme } from "../../theme/ThemeProvider";

// Tudo num gráfico só: a pessoa liga/desliga métricas (pode escolher mais de
// uma) e vê as curvas sobrepostas no mesmo gráfico — dá pra perceber relações
// tipo "a caloria subiu e no dia seguinte a carga também subiu", sem precisar
// abrir uma aba por vez. Com só 1 métrica ligada, mostra o eixo com os
// valores reais; com 2+, cada uma tem unidade diferente (kg, horas, kcal),
// então o eixo some e o gráfico normaliza tudo pra comparar só o formato.
type MetricKey = "peso" | "treino" | "sono" | "dieta" | "carga";

const METRICS: { key: MetricKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "peso", label: "Peso", icon: "scale" },
  { key: "treino", label: "Treino", icon: "barbell" },
  { key: "sono", label: "Sono", icon: "moon" },
  { key: "dieta", label: "Dieta", icon: "restaurant" },
  { key: "carga", label: "Carga", icon: "trending-up" },
];

function metricColor(colors: ReturnType<typeof useTheme>["colors"], key: MetricKey): string {
  return {
    peso: colors.primary,
    treino: colors.moduleTraining,
    sono: colors.moduleSleep,
    dieta: colors.moduleNutrition,
    carga: colors.secondary,
  }[key];
}

function normalize(points: ChartPoint[]): ChartPoint[] {
  if (points.length === 0) return points;
  const ys = points.map((p) => p.y);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  if (min === max) return points.map((p) => ({ ...p, y: 0.5 }));
  return points.map((p) => ({ ...p, y: (p.y - min) / (max - min) }));
}

export function EvolutionScreen() {
  const { colors, type, spacing } = useTheme();
  const route = useRoute<any>();

  const [active, setActive] = useState<Set<MetricKey>>(
    () => new Set<MetricKey>(route.params?.initialMetrics ?? ["peso"])
  );

  const [weight, setWeight] = useState<WeightPoint[]>([]);
  const [volume, setVolume] = useState<VolumePoint[]>([]);
  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [nutritionDays, setNutritionDays] = useState<NutritionDay[]>([]);
  const [exercises, setExercises] = useState<ExerciseOption[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<ExerciseOption | null>(null);
  const [progression, setProgression] = useState<ExerciseProgressionPoint[]>([]);
  const [newWeight, setNewWeight] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function loadAll() {
    const [w, v, s, n, ex] = await Promise.all([
      getWeightEvolution(),
      getVolumeEvolution(),
      listSleepLogs(),
      getNutritionHistory(30),
      getExercisesWithHistory(),
    ]);
    setWeight(w);
    setVolume(v);
    setSleepLogs(s);
    setNutritionDays(n.days);
    setExercises(ex);
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

  function toggle(key: MetricKey) {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Dados brutos por métrica (cada função de acesso já sabe converter sua
  // fonte pra {x: timestamp, y: valor}).
  const rawByMetric: Record<MetricKey, ChartPoint[]> = {
    peso: weight.map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg })),
    treino: volume.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg })),
    sono: sleepLogs.map((l) => ({ x: new Date(l.wake_at).getTime(), y: l.duration_minutes / 60 })),
    dieta: nutritionDays.filter((d) => d.kcal > 0).map((d) => ({ x: new Date(d.date).getTime(), y: d.kcal })),
    carga: progression.map((p) => ({ x: new Date(p.date).getTime(), y: p.max_weight_kg })),
  };

  const activeKeys = useMemo(() => METRICS.map((m) => m.key).filter((k) => active.has(k)), [active]);
  const isMulti = activeKeys.length > 1;

  const chartSeries = activeKeys
    .map((key) => {
      const raw = rawByMetric[key];
      if (raw.length === 0) return null;
      const data = isMulti ? normalize(raw) : raw;
      return { key, data, color: metricColor(colors, key), showDots: !isMulti };
    })
    .filter((s): s is { key: MetricKey; data: ChartPoint[]; color: string; showDots: boolean } => s !== null);

  const singleMetric = !isMulti ? activeKeys[0] : null;
  const singleUnit: Record<MetricKey, (v: number) => string> = {
    peso: (v) => v.toFixed(1),
    treino: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}t` : `${Math.round(v)}`),
    sono: (v) => `${v.toFixed(1)}h`,
    dieta: (v) => `${Math.round(v)}`,
    carga: (v) => `${Math.round(v)}kg`,
  };

  const missingData = activeKeys.filter((k) => rawByMetric[k].length < 2);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Seletor múltiplo — liga quantas métricas quiser, todas aparecem
          sobrepostas no mesmo gráfico embaixo. */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md }}>
        {METRICS.map((m) => {
          const isActive = active.has(m.key);
          const color = metricColor(colors, m.key);
          return (
            <TouchableOpacity
              key={m.key}
              onPress={() => toggle(m.key)}
              activeOpacity={0.85}
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 7,
                paddingVertical: 10,
                paddingHorizontal: 14,
                borderRadius: 14,
                backgroundColor: isActive ? color : colors.surface,
                borderWidth: 1,
                borderColor: isActive ? color : colors.border,
              }}
            >
              <Ionicons name={m.icon} size={20} color={isActive ? colors.textOnPrimary : colors.textSecondary} />
              <Text
                style={[
                  type.caption,
                  { color: isActive ? colors.textOnPrimary : colors.textPrimary, fontWeight: "700" },
                ]}
              >
                {m.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Seletor de exercício — só aparece quando "Carga" está ligada */}
      {active.has("carga") && exercises.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", gap: spacing.xs }}>
            {exercises.map((ex) => {
              const isSel = selectedExercise?.id === ex.id;
              return (
                <TouchableOpacity
                  key={ex.id}
                  onPress={() => setSelectedExercise(ex)}
                  style={{
                    borderRadius: 999,
                    paddingVertical: 8,
                    paddingHorizontal: 14,
                    backgroundColor: isSel ? colors.secondary : colors.surfaceAlt,
                  }}
                >
                  <Text
                    style={[
                      type.caption,
                      { color: isSel ? colors.textOnPrimary : colors.textPrimary, fontWeight: isSel ? "700" : "500" },
                    ]}
                  >
                    {ex.name}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </ScrollView>
      ) : null}

      {/* O gráficozão — todas as métricas ligadas, sobrepostas */}
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
          <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>
            {activeKeys.length === 0 ? "Selecione uma métrica" : "Sua evolução"}
          </Text>
          <HelpDot
            title="Comparando métricas"
            text={
              "Ligue mais de uma métrica pra ver se elas andam juntas — por exemplo, se a caloria sobe um dia e a " +
              "carga sobe no treino seguinte. Com 2 ou mais ligadas, cada curva é normalizada (0 a 100%) pra caberem " +
              "juntas no mesmo gráfico, já que peso, kcal e horas de sono têm escalas bem diferentes. Com só uma " +
              "ligada, os valores reais aparecem no eixo."
            }
          />
        </View>

        {/* Legenda — só precisa quando tem mais de uma curva (com uma só, o
            título "Peso"/"Sono"/etc já deixa claro o que é) */}
        {isMulti ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.sm }}>
            {chartSeries.map((s) => (
              <View key={s.key} style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
                <View style={{ width: 9, height: 9, borderRadius: 5, backgroundColor: s.color }} />
                <Text style={[type.caption, { color: colors.textSecondary }]}>
                  {METRICS.find((m) => m.key === s.key)?.label}
                </Text>
              </View>
            ))}
          </View>
        ) : null}

        {chartSeries.length > 0 ? (
          <LineChart
            height={260}
            series={chartSeries.map((s) => ({ data: s.data, color: s.color, showDots: s.showDots }))}
            showYAxis={!isMulti}
            showMinMax={!isMulti}
            formatY={singleMetric ? singleUnit[singleMetric] : undefined}
          />
        ) : (
          <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.lg, textAlign: "center" }]}>
            {activeKeys.length === 0
              ? "Toque num ícone acima pra ver o gráfico dessa métrica."
              : "Ainda não há dados suficientes para essa métrica."}
          </Text>
        )}

        {missingData.length > 0 && chartSeries.length > 0 ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            {missingData.map((k) => METRICS.find((m) => m.key === k)?.label).join(", ")}{" "}
            {missingData.length === 1 ? "ainda não tem" : "ainda não têm"} dados suficientes.
          </Text>
        ) : null}
      </Card>

      {/* Registrar peso — sempre disponível aqui, é o único lugar do app pra
          isso (diferente de sono/água que têm tela própria). */}
      <Card style={{ marginTop: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
          <Ionicons name="scale" size={18} color={colors.primary} />
          <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, fontSize: 16 }]}>Registrar peso</Text>
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
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
    </ScrollView>
  );
}
