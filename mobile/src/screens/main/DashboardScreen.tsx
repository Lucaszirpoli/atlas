import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, useWindowDimensions, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { listMealsForDay, type MealLog } from "../../api/meals";
import { listRoutines, type Routine } from "../../api/routines";
import { listSleepLogs, type SleepLog } from "../../api/sleep";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { listWorkoutSessions, type WorkoutSessionDetail } from "../../api/workoutSessions";
import { AiFab } from "../../components/AiFab";
import { Avatar } from "../../components/Avatar";
import { ProgressRing } from "../../components/ProgressRing";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}
const MOTIVATION = [
  "Constância vence intensidade 💪",
  "Um treino de cada vez 🔥",
  "Seu único adversário é o de ontem 🚀",
  "Pequenos passos, grandes resultados 🌱",
  "Hoje conta. Sempre conta ✨",
];
function motivationOfTheDay(): string {
  return MOTIVATION[Math.floor(Date.now() / 86400000) % MOTIVATION.length];
}

/** Chave de data local (não-UTC) para comparar dias sem escorregar de fuso. */
function localKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function DashboardScreen() {
  const { colors, type, spacing, isDark, toggleDark } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const { width } = useWindowDimensions();

  const [goal, setGoal] = useState<CalorieGoal | null>(null);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [water, setWater] = useState<WaterSummary | null>(null);
  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [sessions, setSessions] = useState<WorkoutSessionDetail[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);

  async function load() {
    const [g, m, w, s, sess, r] = await Promise.all([
      getCurrentGoal().catch(() => null),
      listMealsForDay(todayIso()).catch(() => []),
      getTodayWaterSummary().catch(() => null),
      listSleepLogs().catch(() => []),
      listWorkoutSessions().catch(() => []),
      listRoutines().catch(() => []),
    ]);
    setGoal(g);
    setMeals(m);
    setWater(w);
    setSleepLogs(s);
    setSessions(sess);
    setRoutines(r);
  }

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  async function quickWater(ml: number) {
    await logWater(ml);
    setWater(await getTodayWaterSummary());
  }

  // ---- Cálculos dos 4 quadrados -------------------------------------------
  const kcalConsumed = meals.reduce((s, m) => s + m.items.reduce((a, i) => a + i.kcal, 0), 0);
  const kcalGoal = goal?.kcal ?? 0;
  const kcalPct = kcalGoal > 0 ? Math.min(kcalConsumed / kcalGoal, 1) : 0;

  const waterMl = water?.total_ml_today ?? 0;
  const waterGoalMl = water?.goal_ml ?? 0;
  const waterPct = waterGoalMl > 0 ? Math.min(waterMl / waterGoalMl, 1) : 0;

  // Treino de hoje: a rotina ativa treinada há mais tempo (ou nunca treinada
  // vem primeiro). É uma sugestão inteligente já que o app não tem agenda fixa.
  const activeRoutines = routines.filter((r) => !r.is_archived);
  function lastTrained(routineId: number): string {
    const times = sessions
      .filter((s) => s.routine_id === routineId && s.completed_at)
      .map((s) => s.completed_at as string);
    return times.length ? times.sort().slice(-1)[0] : "";
  }
  const todayRoutine =
    activeRoutines.length > 0
      ? [...activeRoutines].sort((a, b) => lastTrained(a.id).localeCompare(lastTrained(b.id)))[0]
      : null;

  // Semana atual (domingo → sábado), horas de sono por noite (rótulo = dia que
  // acordou). Não é janela de 7 dias: reseta no domingo.
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);
  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(weekStart.getDate() + i);
    return d;
  });
  const sleepByDay = weekDays.map((day) => {
    const key = localKey(day);
    const log = sleepLogs.find((l) => localKey(new Date(l.wake_at)) === key);
    return log ? log.duration_minutes / 60 : 0;
  });
  const nightsLogged = sleepByDay.filter((h) => h > 0);
  const avgSleep =
    nightsLogged.length > 0 ? nightsLogged.reduce((a, b) => a + b, 0) / nightsLogged.length : 0;

  const firstName = user?.display_name?.split(" ")[0] ?? "";

  // Grid 2×2 de quadrados proporcionais (limita a largura em telas grandes/web
  // pra não virar quadrados gigantes — mantém a cara de app).
  const contentW = Math.min(width - spacing.lg * 2, 520);
  const gap = spacing.md;
  const tile = (contentW - gap) / 2;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={{
          padding: spacing.lg,
          paddingTop: spacing.xl + spacing.md,
          paddingBottom: spacing.lg,
          alignItems: "center",
          flexGrow: 1,
        }}
        showsVerticalScrollIndicator={false}
      >
        {/* Topo: saudação + toggle de tema + social + perfil */}
        <View
          style={{
            width: contentW,
            flexDirection: "row",
            alignItems: "center",
            marginBottom: spacing.lg,
          }}
        >
          <View style={{ flex: 1, marginRight: spacing.sm }}>
            <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22 }]}>
              {greeting()}, {firstName}
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
              {motivationOfTheDay()}
            </Text>
          </View>
          <IconButton
            icon={isDark ? "sunny" : "moon"}
            tint={isDark ? colors.warning : colors.moduleSleep}
            onPress={toggleDark}
          />
          <IconButton icon="people" tint={colors.moduleSocial} onPress={() => navigation.navigate("Social")} />
          <TouchableOpacity onPress={() => navigation.navigate("Profile")}>
            <Avatar name={user?.display_name ?? "?"} handle={user?.handle ?? "?"} size={44} />
          </TouchableOpacity>
        </View>

        {/* Grid 2×2 — os quadrados crescem pra preencher a altura da tela
            (sem sobrar espaço vazio embaixo no celular). minHeight garante o
            tamanho mínimo quadrado em telas curtas (aí a tela rola). */}
        <View style={{ width: contentW, flex: 1, gap, minHeight: tile * 2 + gap }}>
          <View style={{ flexDirection: "row", gap, flex: 1 }}>
          {/* Água — barra horizontal */}
          <Tile minH={tile} onPress={() => navigation.navigate("Water")}>
            <TileHeader icon="water" tint={colors.info} title="Água" />
            <View style={{ flex: 1, justifyContent: "center" }}>
              <Text style={[type.display, { color: colors.textPrimary, fontSize: 34, lineHeight: 38 }]}>
                {(waterMl / 1000).toFixed(1)}
                <Text style={[type.h2, { color: colors.textSecondary }]}> L</Text>
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary }]}>
                de {(waterGoalMl / 1000).toFixed(1)} L · {Math.round(waterPct * 100)}%
              </Text>
            </View>
            <View style={{ height: 10, backgroundColor: colors.surfaceAlt, borderRadius: 5 }}>
              <View
                style={{
                  height: 10,
                  width: `${waterPct * 100}%`,
                  backgroundColor: colors.info,
                  borderRadius: 5,
                }}
              />
            </View>
            <View style={{ flexDirection: "row", gap: spacing.xs, marginTop: spacing.sm }}>
              {[200, 300, 500].map((ml) => (
                <TouchableOpacity
                  key={ml}
                  onPress={() => quickWater(ml)}
                  style={{
                    flex: 1,
                    alignItems: "center",
                    paddingVertical: 7,
                    borderRadius: 999,
                    backgroundColor: colors.info + "18",
                  }}
                >
                  <Text style={[type.caption, { color: colors.info, fontWeight: "800" }]}>+{ml}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </Tile>

          {/* Calorias — anel circular */}
          <Tile minH={tile} onPress={() => navigation.navigate("NutritionModule")}>
            <TileHeader icon="restaurant" tint={colors.moduleNutrition} title="Calorias" />
            <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
              <ProgressRing
                progress={kcalPct}
                size={Math.min(tile - 60, 128)}
                strokeWidth={12}
                color={colors.moduleNutrition}
                value={kcalGoal > 0 ? `${Math.round(kcalConsumed)}` : "—"}
                label={kcalGoal > 0 ? `${Math.round(kcalPct * 100)}% de ${Math.round(kcalGoal)}` : "definir meta"}
              />
            </View>
          </Tile>
          </View>

          <View style={{ flexDirection: "row", gap, flex: 1 }}>
          {/* Sono — gráfico da semana atual */}
          <Tile minH={tile} onPress={() => navigation.navigate("Sleep")}>
            <TileHeader icon="moon" tint={colors.moduleSleep} title="Sono" />
            <View style={{ flex: 1, justifyContent: "flex-end" }}>
              <WeekSleepChart hours={sleepByDay} />
            </View>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
              {avgSleep > 0
                ? `média ${Math.floor(avgSleep)}h${String(Math.round((avgSleep % 1) * 60)).padStart(2, "0")} esta semana`
                : "sem registros esta semana"}
            </Text>
          </Tile>

          {/* Treino — treino de hoje */}
          <Tile minH={tile} onPress={() => navigation.navigate("TrainingModule")}>
            <TileHeader icon="barbell" tint={colors.moduleTraining} title="Treino" />
            <View style={{ flex: 1, justifyContent: "center" }}>
              <Text style={[type.caption, { color: colors.textSecondary, marginBottom: 2 }]}>
                {todayRoutine ? "Treino de hoje" : "Sem rotina ainda"}
              </Text>
              <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22 }]} numberOfLines={2}>
                {todayRoutine ? todayRoutine.name : "Montar rotina"}
              </Text>
              {todayRoutine ? (
                <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>
                  {todayRoutine.exercises.length}{" "}
                  {todayRoutine.exercises.length === 1 ? "exercício" : "exercícios"}
                </Text>
              ) : null}
            </View>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 4,
                alignSelf: "flex-start",
                backgroundColor: colors.moduleTraining + "18",
                borderRadius: 999,
                paddingVertical: 6,
                paddingHorizontal: 12,
              }}
            >
              <Ionicons
                name={todayRoutine ? "play" : "add"}
                size={14}
                color={colors.moduleTraining}
              />
              <Text style={[type.caption, { color: colors.moduleTraining, fontWeight: "800" }]}>
                {todayRoutine ? "Começar" : "Criar"}
              </Text>
            </View>
          </Tile>
          </View>
        </View>
      </ScrollView>
      <AiFab />
    </View>
  );
}

// --- Blocos reutilizáveis ---------------------------------------------------

function IconButton({
  icon,
  tint,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  tint: string;
  onPress: () => void;
}) {
  const { colors, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      style={{
        width: 44,
        height: 44,
        borderRadius: 15,
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
        alignItems: "center",
        justifyContent: "center",
        marginRight: spacing.sm,
      }}
    >
      <Ionicons name={icon} size={20} color={tint} />
    </TouchableOpacity>
  );
}

function Tile({
  minH,
  onPress,
  children,
}: {
  minH: number;
  onPress: () => void;
  children: React.ReactNode;
}) {
  const { colors, spacing, shadow } = useTheme();
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress} style={{ flex: 1 }}>
      <View
        style={[
          {
            flex: 1,
            minHeight: minH,
            backgroundColor: colors.surface,
            borderRadius: 22,
            padding: spacing.md,
          },
          shadow.sm,
        ]}
      >
        {children}
      </View>
    </TouchableOpacity>
  );
}

function TileHeader({
  icon,
  tint,
  title,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  tint: string;
  title: string;
}) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
      <View
        style={{
          width: 30,
          height: 30,
          borderRadius: 10,
          backgroundColor: tint + "22",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Ionicons name={icon} size={17} color={tint} />
      </View>
      <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16 }]}>{title}</Text>
    </View>
  );
}

/** Barrinhas da semana atual (dom→sáb). Cor = saúde do sono da noite. */
function WeekSleepChart({ hours }: { hours: number[] }) {
  const { colors, type } = useTheme();
  const labels = ["D", "S", "T", "Q", "Q", "S", "S"];
  const maxH = 52; // altura máxima da barra
  const cap = 9; // 9h = barra cheia

  function barColor(h: number): string {
    if (h <= 0) return colors.surfaceAlt;
    if (h >= 7) return colors.success;
    if (h >= 5) return colors.warning;
    return colors.danger;
  }

  const todayIdx = new Date().getDay();

  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between" }}>
      {hours.map((h, i) => {
        const barH = h > 0 ? Math.max((Math.min(h, cap) / cap) * maxH, 6) : 6;
        const isToday = i === todayIdx;
        return (
          <View key={i} style={{ alignItems: "center", flex: 1 }}>
            <View
              style={{
                width: "62%",
                height: maxH,
                justifyContent: "flex-end",
                borderRadius: 5,
              }}
            >
              <View
                style={{
                  height: barH,
                  borderRadius: 5,
                  backgroundColor: barColor(h),
                }}
              />
            </View>
            <Text
              style={[
                type.caption,
                {
                  fontSize: 11,
                  marginTop: 4,
                  color: isToday ? colors.textPrimary : colors.textSecondary,
                  fontWeight: isToday ? "800" : "400",
                },
              ]}
            >
              {labels[i]}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
