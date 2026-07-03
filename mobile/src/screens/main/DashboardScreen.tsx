import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { listMealsForDay, type MealLog } from "../../api/meals";
import { listSleepLogs, type SleepLog } from "../../api/sleep";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { listWorkoutSessions, type WorkoutSessionDetail } from "../../api/workoutSessions";
import { AiFab } from "../../components/AiFab";
import { Avatar } from "../../components/Avatar";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
function startOfWeekIso(): string {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
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

export function DashboardScreen() {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [goal, setGoal] = useState<CalorieGoal | null>(null);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [water, setWater] = useState<WaterSummary | null>(null);
  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [sessions, setSessions] = useState<WorkoutSessionDetail[]>([]);

  async function load() {
    const [g, m, w, s, sess] = await Promise.all([
      getCurrentGoal().catch(() => null),
      listMealsForDay(todayIso()).catch(() => []),
      getTodayWaterSummary().catch(() => null),
      listSleepLogs().catch(() => []),
      listWorkoutSessions().catch(() => []),
    ]);
    setGoal(g);
    setMeals(m);
    setWater(w);
    setSleepLogs(s);
    setSessions(sess);
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

  const kcalConsumed = meals.reduce((s, m) => s + m.items.reduce((a, i) => a + i.kcal, 0), 0);
  const kcalGoal = goal?.kcal ?? 0;
  const kcalPct = kcalGoal > 0 ? Math.min(kcalConsumed / kcalGoal, 1) : 0;

  const weekStart = startOfWeekIso();
  const workoutsThisWeek = sessions.filter((s) => s.completed_at && s.completed_at >= weekStart).length;
  const lastSleep = sleepLogs[0];
  const waterPct = water && water.goal_ml > 0 ? Math.min(water.total_ml_today / water.goal_ml, 1) : 0;

  const firstName = user?.display_name?.split(" ")[0] ?? "";

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.xl + spacing.md, paddingBottom: spacing.xxl }}
        showsVerticalScrollIndicator={false}
      >
        {/* Topo: saudação + perfil/social no canto */}
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.lg }}>
          <View style={{ flex: 1 }}>
            <Text style={[type.h1, { color: colors.textPrimary, fontSize: 26 }]}>
              {greeting()}, {firstName}
            </Text>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{motivationOfTheDay()}</Text>
          </View>
          <TouchableOpacity
            onPress={() => navigation.navigate("Social")}
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
            <Ionicons name="people" size={20} color={colors.moduleSocial} />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigation.navigate("Profile")}>
            <Avatar name={user?.display_name ?? "?"} handle={user?.handle ?? "?"} size={44} />
          </TouchableOpacity>
        </View>

        {/* FAIXA: Dieta */}
        <Band
          color={colors.moduleNutrition}
          icon="restaurant"
          title="Dieta"
          value={kcalGoal > 0 ? `${Math.round(kcalConsumed)} / ${Math.round(kcalGoal)} kcal` : "Definir meta"}
          progress={kcalPct}
          onPress={() => navigation.navigate("NutritionModule")}
        />

        {/* FAIXA: Treino */}
        <Band
          color={colors.moduleTraining}
          icon="barbell"
          title="Treino"
          value={`${workoutsThisWeek} ${workoutsThisWeek === 1 ? "treino" : "treinos"} essa semana`}
          onPress={() => navigation.navigate("TrainingModule")}
        />

        {/* FAIXA: Sono */}
        <Band
          color={colors.moduleSleep}
          icon="moon"
          title="Sono"
          value={
            lastSleep
              ? `${Math.floor(lastSleep.duration_minutes / 60)}h${String(lastSleep.duration_minutes % 60).padStart(2, "0")} · última noite`
              : "Registrar sua noite"
          }
          onPress={() => navigation.navigate("Sleep")}
        />

        {/* FAIXA: Água (com ação rápida embutida) */}
        <View
          style={[
            {
              backgroundColor: colors.surface,
              borderRadius: 20,
              padding: spacing.lg,
              marginBottom: spacing.md,
            },
            shadow.sm,
          ]}
        >
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={() => navigation.navigate("Water")}
            style={{ flexDirection: "row", alignItems: "center" }}
          >
            <View
              style={{
                width: 52,
                height: 52,
                borderRadius: 18,
                backgroundColor: colors.info + "22",
                alignItems: "center",
                justifyContent: "center",
                marginRight: spacing.md,
              }}
            >
              <Ionicons name="water" size={26} color={colors.info} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[type.h2, { color: colors.textPrimary }]}>Água</Text>
              <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                {((water?.total_ml_today ?? 0) / 1000).toFixed(1)}L de {((water?.goal_ml ?? 0) / 1000).toFixed(1)}L
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
          {/* barra + botões rápidos */}
          <View style={{ height: 8, backgroundColor: colors.surfaceAlt, borderRadius: 4, marginTop: spacing.md }}>
            <View style={{ height: 8, width: `${waterPct * 100}%`, backgroundColor: colors.info, borderRadius: 4 }} />
          </View>
          <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
            {[200, 300, 500].map((ml) => (
              <TouchableOpacity
                key={ml}
                onPress={() => quickWater(ml)}
                style={{
                  flex: 1,
                  alignItems: "center",
                  paddingVertical: 10,
                  borderRadius: 999,
                  backgroundColor: colors.info + "18",
                }}
              >
                <Text style={[type.bodySmall, { color: colors.info, fontWeight: "800" }]}>+{ml}ml</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </ScrollView>
      <AiFab />
    </View>
  );
}

function Band({
  color,
  icon,
  title,
  value,
  progress,
  onPress,
}: {
  color: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  value: string;
  progress?: number;
  onPress: () => void;
}) {
  const { colors, type, spacing, shadow } = useTheme();
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress} style={{ marginBottom: spacing.md }}>
      <View style={[{ backgroundColor: colors.surface, borderRadius: 20, padding: spacing.lg }, shadow.sm]}>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <View
            style={{
              width: 52,
              height: 52,
              borderRadius: 18,
              backgroundColor: color + "22",
              alignItems: "center",
              justifyContent: "center",
              marginRight: spacing.md,
            }}
          >
            <Ionicons name={icon} size={26} color={color} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.h2, { color: colors.textPrimary }]}>{title}</Text>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{value}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
        </View>
        {progress !== undefined ? (
          <View style={{ height: 8, backgroundColor: colors.surfaceAlt, borderRadius: 4, marginTop: spacing.md }}>
            <View style={{ height: 8, width: `${progress * 100}%`, backgroundColor: color, borderRadius: 4 }} />
          </View>
        ) : null}
      </View>
    </TouchableOpacity>
  );
}
