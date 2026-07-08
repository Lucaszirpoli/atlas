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

// "treino" é o VOLUME da sessão (peso × reps somado de todas as séries) — por
// isso o rótulo é "Volume", não "Treino" (que dava a entender frequência).
const METRICS: { key: MetricKey; label: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { key: "peso", label: "Peso", icon: "scale" },
  { key: "treino", label: "Volume", icon: "barbell" },
  { key: "sono", label: "Sono", icon: "moon" },
  { key: "dieta", label: "Dieta", icon: "restaurant" },
  { key: "carga", label: "Carga", icon: "trending-up" },
];

// Uma linha explicando o que cada métrica é e em que unidade — aparece de
// subtítulo quando a pessoa está vendo uma métrica só.
const METRIC_DESC: Record<MetricKey, string> = {
  peso: "Seu peso corporal, em kg.",
  treino: "Peso total levantado no treino (peso × reps de todas as séries), em kg/toneladas.",
  sono: "Horas dormidas por noite.",
  dieta: "Calorias consumidas por dia (kcal).",
  carga: "Maior peso levantado no exercício escolhido, em kg.",
};

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

// Sobreposição estilo mercado financeiro: cada métrica vira "% de variação
// desde o início do período" — todas as curvas PARTEM do mesmo ponto (0%) e
// dividem UMA escala só, então +5% significa a mesma coisa pra dieta, carga
// ou sono, e dá pra ler direto quem subiu/caiu mais. Bônus: como % é uma
// unidade comum a todas, o eixo Y volta a fazer sentido no modo comparação
// (ex: -5%, 0%, +10%) em vez de sumir.
function toPercentChange(points: ChartPoint[]): ChartPoint[] {
  if (points.length === 0) return points;
  const base = points[0].y;
  if (base === 0) return points.map((p) => ({ ...p, y: 0 }));
  return points.map((p) => ({ ...p, y: (p.y / base - 1) * 100 }));
}

// ---------------------------------------------------------------------------
// Análise automática — 100% calculada dos registros reais do período, sem
// nada inventado. Cada observação só entra se tiver amostra suficiente
// (>= 2 dias de cada lado da comparação) E diferença relevante (>= 4%);
// senão, fica de fora — melhor não dizer nada do que dizer algo fraco.
// Tom sempre informativo, nunca de culpa (espec. 3.7): "volume foi menor",
// nunca "falhou". Correlação não é causa — o HelpDot avisa isso.
// ---------------------------------------------------------------------------

type Insight = { icon: keyof typeof Ionicons.glyphMap; text: string };

function dayKeyOf(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}
function shiftDay(key: string, n: number): string {
  const d = new Date(`${key}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
const avg = (ns: number[]) => ns.reduce((a, b) => a + b, 0) / ns.length;
const fmtVol = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)}t` : `${Math.round(v)}kg`);

function buildInsights(args: {
  sleep: { day: string; hours: number }[]; // day = dia em que acordou
  kcal: { day: string; kcal: number }[];
  vol: { day: string; volume: number }[]; // volume da sessão de treino
  weightPts: ChartPoint[]; // ordem cronológica
  carga: ChartPoint[]; // progressão do exercício selecionado
  cargaName: string | null;
}): Insight[] {
  const out: Insight[] = [];
  const kcalMap = new Map(args.kcal.map((d) => [d.day, d.kcal]));
  const volMap = new Map(args.vol.map((d) => [d.day, d.volume]));
  const shortNights = args.sleep.filter((s) => s.hours < 7);
  const goodNights = args.sleep.filter((s) => s.hours >= 7);

  // Compara a média de uma métrica nos dias ligados a noites curtas (<7h) vs
  // noites boas. Testa tanto o dia do acordar quanto o dia seguinte (o efeito
  // de dormir mal às vezes só aparece depois) e usa o mais forte que passar
  // nos critérios de amostra/diferença.
  function sleepEffect(map: Map<string, number>) {
    let best: { diff: number; a: number; b: number; shifted: boolean } | null = null;
    for (const shift of [0, 1]) {
      const after = shortNights.map((s) => map.get(shiftDay(s.day, shift))).filter((v): v is number => v != null);
      const base = goodNights.map((s) => map.get(shiftDay(s.day, shift))).filter((v): v is number => v != null);
      if (after.length < 2 || base.length < 2) continue;
      const a = avg(after);
      const b = avg(base);
      if (b === 0) continue;
      const diff = (a / b - 1) * 100;
      if (Math.abs(diff) < 4) continue;
      if (!best || Math.abs(diff) > Math.abs(best.diff)) best = { diff, a, b, shifted: shift === 1 };
    }
    return best;
  }

  const sonoKcal = sleepEffect(kcalMap);
  if (sonoKcal) {
    const prefix = sonoKcal.shifted ? "No dia seguinte a dormir menos de 7h" : "Nos dias em que dormiu menos de 7h";
    out.push({
      icon: "moon",
      text: `${prefix}, você comeu em média ${Math.round(Math.abs(sonoKcal.diff))}% ${
        sonoKcal.diff > 0 ? "a mais" : "a menos"
      } (${Math.round(sonoKcal.a)} vs ${Math.round(sonoKcal.b)} kcal).`,
    });
  }

  const sonoVol = sleepEffect(volMap);
  if (sonoVol) {
    const prefix = sonoVol.shifted ? "No treino do dia seguinte a dormir menos de 7h" : "Nos treinos de dias com menos de 7h de sono";
    out.push({
      icon: "barbell",
      text: `${prefix}, seu volume foi em média ${Math.round(Math.abs(sonoVol.diff))}% ${
        sonoVol.diff > 0 ? "maior" : "menor"
      } (${fmtVol(sonoVol.a)} vs ${fmtVol(sonoVol.b)}).`,
    });
  }

  // Caloria do dia anterior → volume do treino: separa os treinos entre
  // "véspera acima da mediana de kcal" e "abaixo" e compara as médias.
  const kcalVals = args.kcal.map((d) => d.kcal).sort((x, y) => x - y);
  if (kcalVals.length >= 4) {
    const median = kcalVals[Math.floor(kcalVals.length / 2)];
    const hi: number[] = [];
    const lo: number[] = [];
    for (const v of args.vol) {
      const prev = kcalMap.get(shiftDay(v.day, -1));
      if (prev == null) continue;
      (prev > median ? hi : lo).push(v.volume);
    }
    if (hi.length >= 2 && lo.length >= 2) {
      const diff = (avg(hi) / avg(lo) - 1) * 100;
      if (Math.abs(diff) >= 4) {
        out.push({
          icon: "restaurant",
          text: `Nos treinos após dias comendo acima de ~${Math.round(median)} kcal, seu volume foi em média ${Math.round(
            Math.abs(diff)
          )}% ${diff > 0 ? "maior" : "menor"} (${fmtVol(avg(hi))} vs ${fmtVol(avg(lo))}).`,
        });
      }
    }
  }

  // Tendências simples no período (primeira metade vs segunda, início vs fim)
  if (args.vol.length >= 4) {
    const half = Math.floor(args.vol.length / 2);
    const first = avg(args.vol.slice(0, half).map((v) => v.volume));
    const second = avg(args.vol.slice(half).map((v) => v.volume));
    const diff = (second / first - 1) * 100;
    if (Math.abs(diff) >= 3) {
      out.push({
        icon: diff > 0 ? "trending-up" : "trending-down",
        text: `Seu volume de treino ${diff > 0 ? "subiu" : "caiu"} ~${Math.round(Math.abs(diff))}% ao longo do período (média de ${fmtVol(
          first
        )} → ${fmtVol(second)} por treino).`,
      });
    }
  }

  if (args.carga.length >= 2 && args.cargaName) {
    const first = args.carga[0].y;
    const last = args.carga[args.carga.length - 1].y;
    if (first > 0 && Math.abs(last - first) >= 0.5) {
      out.push({
        icon: "barbell",
        text: `No ${args.cargaName}, sua carga foi de ${Math.round(first)}kg para ${Math.round(last)}kg (${
          last >= first ? "+" : ""
        }${Math.round((last / first - 1) * 100)}%).`,
      });
    }
  }

  if (args.weightPts.length >= 2) {
    const first = args.weightPts[0].y;
    const last = args.weightPts[args.weightPts.length - 1].y;
    const delta = last - first;
    out.push({
      icon: "scale",
      text:
        Math.abs(delta) >= 0.3
          ? `Seu peso ${delta < 0 ? "caiu" : "subiu"} ${Math.abs(delta).toFixed(1)}kg no período (${first.toFixed(1)} → ${last.toFixed(1)}kg).`
          : `Seu peso ficou estável no período (${first.toFixed(1)} → ${last.toFixed(1)}kg).`,
    });
  }

  if (args.sleep.length >= 3) {
    const m = avg(args.sleep.map((s) => s.hours));
    out.push({
      icon: "moon",
      text: `Média de sono: ${m.toFixed(1)}h por noite${
        shortNights.length > 0 ? ` — ${shortNights.length} ${shortNights.length === 1 ? "noite" : "noites"} abaixo de 7h` : ""
      }.`,
    });
  }

  return out.slice(0, 5);
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
      const data = isMulti ? toPercentChange(filled) : filled;
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

  // Análise automática do período — recalculada quando os dados ou a janela
  // (7/15/30d) mudam. Tudo derivado dos registros reais; ver buildInsights.
  const analysis = useMemo(() => {
    const sleepDays = sleepLogs
      .filter((l) => new Date(l.wake_at).getTime() >= cutoff)
      .map((l) => ({ day: dayKeyOf(l.wake_at), hours: l.duration_minutes / 60 }));
    const kcalDays = nutritionDays
      .filter((d) => d.kcal > 0 && new Date(d.date).getTime() >= cutoff)
      .map((d) => ({ day: d.date, kcal: d.kcal }));
    const volDays = volume
      .filter((v) => new Date(v.date).getTime() >= cutoff)
      .map((v) => ({ day: dayKeyOf(v.date), volume: v.volume_kg }));
    const weightPts = weight
      .map((p) => ({ x: new Date(p.date).getTime(), y: p.weight_kg }))
      .filter((p) => p.x >= cutoff);
    const cargaPts = progression
      .map((p) => ({ x: new Date(p.date).getTime(), y: p.max_weight_kg }))
      .filter((p) => p.x >= cutoff);
    const hasAnyData = sleepDays.length + kcalDays.length + volDays.length + weightPts.length > 0;
    return {
      hasAnyData,
      insights: buildInsights({
        sleep: sleepDays,
        kcal: kcalDays,
        vol: volDays,
        weightPts,
        carga: cargaPts,
        cargaName: selectedExercise?.name ?? null,
      }),
    };
  }, [sleepLogs, nutritionDays, volume, weight, progression, selectedExercise, cutoff]);

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
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>
              {activeKeys.length === 0 ? "Selecione uma métrica" : "Sua evolução"}
            </Text>
            <HelpDot
              title="Comparando métricas"
              text={
                "Ligue mais de uma métrica pra ver se elas andam juntas — por exemplo, se a caloria sobe um dia e a " +
                "carga sobe no treino seguinte. Com 2 ou mais ligadas, funciona como comparação de ações no mercado " +
                "financeiro: todas as curvas partem de 0% e o gráfico mostra a variação percentual de cada uma desde " +
                "o início do período, numa escala única — +5% significa a mesma coisa pra dieta, carga ou sono. Com " +
                "só uma métrica, os valores reais aparecem nos eixos. Se algum dia ficou sem registro, a linha segue " +
                "reta com o último valor até o próximo — nunca some nem quebra."
              }
            />
          </View>
          {/* Subtítulo: com uma métrica só, explica o que ela é e a unidade. */}
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.sm }]}>
            {singleMetric
              ? METRIC_DESC[singleMetric]
              : activeKeys.length > 1
                ? "Variação % desde o início do período — todas partem de 0% na mesma escala."
                : "Toque nos ícones pra escolher o que ver."}
          </Text>

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
              showYAxis
              highlightZero={isMulti}
              formatY={
                singleMetric
                  ? singleUnit[singleMetric]
                  : (v) => `${v > 0 ? "+" : ""}${Math.round(v)}%`
              }
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

      {/* Análise automática — observações calculadas dos registros reais do
          período. Nada de texto inventado: cada linha vem de uma comparação
          estatística que passou nos critérios de amostra/diferença. */}
      {analysis.hasAnyData ? (
        <Card style={{ marginTop: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="analytics" size={18} color={colors.secondary} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, fontSize: 16, flex: 1 }]}>
              Análise do período
            </Text>
            <HelpDot
              title="Análise automática"
              text={
                "Essas observações são calculadas direto dos seus registros reais no período selecionado — nada é " +
                "inventado. Uma relação só aparece se tiver dias suficientes de amostra dos dois lados da comparação " +
                "e uma diferença relevante; senão ela fica de fora. E lembre: correlação não é causa — use como pista " +
                "pra se observar, não como veredito."
              }
            />
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.sm }]}>
            Calculada dos seus registros dos últimos {rangeDays} dias.
          </Text>
          {analysis.insights.length > 0 ? (
            analysis.insights.map((ins, i) => (
              <View
                key={i}
                style={{ flexDirection: "row", gap: spacing.sm, marginTop: i === 0 ? 0 : spacing.sm, alignItems: "flex-start" }}
              >
                <Ionicons name={ins.icon} size={15} color={colors.textSecondary} style={{ marginTop: 2 }} />
                <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>{ins.text}</Text>
              </View>
            ))
          ) : (
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
              Ainda não encontrei relações claras nesse período — continue registrando treino, sono e dieta que a
              análise vai ficando mais rica.
            </Text>
          )}
        </Card>
      ) : null}

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
