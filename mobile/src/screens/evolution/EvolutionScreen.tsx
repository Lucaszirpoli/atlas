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

const RANGE_OPTIONS = [7, 15, 30] as const;
type RangeDays = (typeof RANGE_OPTIONS)[number];

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
  const [rangeDays, setRangeDays] = useState<RangeDays>(30);

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

  const allActive = METRICS.every((m) => active.has(m.key));
  function toggleAll() {
    setActive(allActive ? new Set() : new Set(METRICS.map((m) => m.key)));
  }

  // Dados brutos por métrica (cada função de acesso já sabe converter sua
  // fonte pra {x: timestamp, y: valor}), recortados pelo período escolhido
  // (7/15/30 dias) — todas as métricas usam a mesma janela de tempo.
  const cutoff = Date.now() - rangeDays * 24 * 60 * 60 * 1000;
  const inRange = (p: ChartPoint) => p.x >= cutoff;

  const rawByMetric: Record<MetricKey, ChartPoint[]> = {
    peso: weight.map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg })).filter(inRange),
    treino: volume.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg })).filter(inRange),
    sono: sleepLogs
      .map((l) => ({ x: new Date(l.wake_at).getTime(), y: l.duration_minutes / 60 }))
      .filter(inRange),
    dieta: nutritionDays
      .filter((d) => d.kcal > 0)
      .map((d) => ({ x: new Date(d.date).getTime(), y: d.kcal }))
      .filter(inRange),
    carga: progression.map((p) => ({ x: new Date(p.date).getTime(), y: p.max_weight_kg })).filter(inRange),
  };

  const activeKeys = useMemo(() => METRICS.map((m) => m.key).filter((k) => active.has(k)), [active]);
  const isMulti = activeKeys.length > 1;

  // "Carrega" o último valor conhecido até hoje: se a pessoa registrou carga
  // na segunda mas não terça/quarta, o gráfico estende uma linha horizontal
  // até hoje no mesmo valor — em vez de a linha parar no meio ou a métrica
  // sumir. Cada métrica pode ter dias faltando sem bagunçar o gráfico; todas
  // se encaixam na mesma linha do tempo, terminando em "hoje".
  const nowX = Date.now();
  function fillToNow(points: ChartPoint[]): ChartPoint[] {
    if (points.length === 0) return points;
    const sorted = [...points].sort((a, b) => a.x - b.x);
    const last = sorted[sorted.length - 1];
    if (nowX - last.x > 12 * 60 * 60 * 1000) {
      return [...sorted, { x: nowX, y: last.y }];
    }
    return sorted;
  }

  const chartSeries = activeKeys
    .map((key) => {
      const filled = fillToNow(rawByMetric[key]);
      if (filled.length === 0) return null;
      const data = isMulti ? normalize(filled) : filled;
      return { key, data, color: metricColor(colors, key), showDots: !isMulti && data.length <= 12 };
    })
    .filter((s): s is { key: MetricKey; data: ChartPoint[]; color: string; showDots: boolean } => s !== null);

  const singleMetric = !isMulti ? activeKeys[0] : null;
  const singleUnit: Record<MetricKey, (v: number) => string> = {
    peso: (v) => `${v.toFixed(1)}kg`,
    treino: (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}t` : `${Math.round(v)}`),
    sono: (v) => `${v.toFixed(1)}h`,
    dieta: (v) => `${(v / 1000).toFixed(1)}k`,
    carga: (v) => `${Math.round(v)}kg`,
  };

  const missingData = activeKeys.filter((k) => rawByMetric[k].length === 0);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Seletor múltiplo — liga quantas métricas quiser, todas aparecem
          sobrepostas no mesmo gráfico embaixo. "Todos" liga/desliga tudo
          de uma vez. */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.sm }}>
        <TouchableOpacity
          onPress={toggleAll}
          activeOpacity={0.85}
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 7,
            paddingVertical: 10,
            paddingHorizontal: 14,
            borderRadius: 14,
            backgroundColor: allActive ? colors.textPrimary : colors.surface,
            borderWidth: 1,
            borderColor: allActive ? colors.textPrimary : colors.border,
          }}
        >
          <Ionicons name="apps" size={20} color={allActive ? colors.bg : colors.textSecondary} />
          <Text
            style={[type.caption, { color: allActive ? colors.bg : colors.textPrimary, fontWeight: "700" }]}
          >
            Todos
          </Text>
        </TouchableOpacity>
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

      {/* Seletor de período — mesma janela pra todas as métricas ligadas */}
      <View style={{ flexDirection: "row", gap: spacing.xs, marginBottom: spacing.md }}>
        {RANGE_OPTIONS.map((d) => {
          const isSel = rangeDays === d;
          return (
            <TouchableOpacity
              key={d}
              onPress={() => setRangeDays(d)}
              activeOpacity={0.85}
              style={{
                paddingVertical: 7,
                paddingHorizontal: 14,
                borderRadius: 999,
                backgroundColor: isSel ? colors.surfaceAlt : "transparent",
                borderWidth: 1,
                borderColor: isSel ? colors.border : "transparent",
              }}
            >
              <Text
                style={[
                  type.caption,
                  { color: isSel ? colors.textPrimary : colors.textSecondary, fontWeight: isSel ? "700" : "500" },
                ]}
              >
                {d} dias
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

      {/* O gráficozão — todas as métricas ligadas, sobrepostas. Card sem
          padding lateral pra o gráfico usar a largura toda (só o texto tem
          recuo); assim a linha aproveita a área cinza inteira. */}
      <Card padded={false} style={{ paddingVertical: spacing.lg }}>
        <View style={{ paddingHorizontal: spacing.lg }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>
              {activeKeys.length === 0 ? "Selecione uma métrica" : "Sua evolução"}
            </Text>
            <HelpDot
              title="Comparando métricas"
              text={
                "Ligue mais de uma métrica pra ver se elas andam juntas — por exemplo, se a caloria sobe um dia e a " +
                "carga sobe no treino seguinte. Com 2 ou mais ligadas, cada curva é normalizada (0 a 100%) pra caberem " +
                "juntas no mesmo gráfico, já que peso, kcal e horas de sono têm escalas bem diferentes. Com só uma, os " +
                "valores reais aparecem nos eixos. Se algum dia ficou sem registro, a linha segue reta com o último " +
                "valor até o próximo registro — nunca some nem quebra."
              }
            />
          </View>

          {/* Legenda — só precisa quando tem mais de uma curva */}
          {isMulti ? (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.xs }}>
              {chartSeries.map((s) => (
                <View key={s.key} style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
                  <View style={{ width: 10, height: 3, borderRadius: 2, backgroundColor: s.color }} />
                  <Text style={[type.caption, { color: colors.textSecondary }]}>
                    {METRICS.find((m) => m.key === s.key)?.label}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>

        {chartSeries.length > 0 ? (
          <View style={{ paddingHorizontal: spacing.sm }}>
            <LineChart
              height={240}
              series={chartSeries.map((s) => ({
                data: s.data,
                color: s.color,
                showDots: s.showDots,
                area: !isMulti,
              }))}
              showYAxis={!isMulti}
              formatY={singleMetric ? singleUnit[singleMetric] : undefined}
            />
          </View>
        ) : (
          <Text
            style={[
              type.bodySmall,
              { color: colors.textSecondary, paddingVertical: spacing.lg, paddingHorizontal: spacing.lg, textAlign: "center" },
            ]}
          >
            {activeKeys.length === 0
              ? "Toque num ícone acima pra ver o gráfico dessa métrica."
              : "Ainda não há registros dessa métrica no período."}
          </Text>
        )}

        {missingData.length > 0 && chartSeries.length > 0 ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, paddingHorizontal: spacing.lg }]}>
            {missingData.map((k) => METRICS.find((m) => m.key === k)?.label).join(", ")}{" "}
            {missingData.length === 1 ? "não tem" : "não têm"} registro no período.
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
