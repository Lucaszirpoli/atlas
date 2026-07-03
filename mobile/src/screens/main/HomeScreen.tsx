import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { listMealsForDay, type MealLog } from "../../api/meals";
import { listSleepLogs, type SleepLog } from "../../api/sleep";
import { getTodayWaterSummary, type WaterSummary } from "../../api/water";
import { listWorkoutSessions, type WorkoutSessionDetail } from "../../api/workoutSessions";
import { Card } from "../../components/Card";
import { ProgressRing } from "../../components/ProgressRing";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

function startOfWeekIso(): string {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

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
  "Disciplina é liberdade 🧠",
  "Corpo forte, mente forte ⚡",
];

function motivationOfTheDay(): string {
  const dayIndex = Math.floor(Date.now() / 86400000) % MOTIVATION.length;
  return MOTIVATION[dayIndex];
}

export function HomeScreen() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [goal, setGoal] = useState<CalorieGoal | null>(null);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [water, setWater] = useState<WaterSummary | null>(null);
  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [sessions, setSessions] = useState<WorkoutSessionDetail[]>([]);

  useFocusEffect(
    useCallback(() => {
      getCurrentGoal().then(setGoal).catch(() => {});
      listMealsForDay(todayIso()).then(setMeals).catch(() => {});
      getTodayWaterSummary().then(setWater).catch(() => {});
      listSleepLogs().then(setSleepLogs).catch(() => {});
      listWorkoutSessions().then(setSessions).catch(() => {});
    }, [])
  );

  const kcalConsumed = meals.reduce((s, m) => s + m.items.reduce((a, i) => a + i.kcal, 0), 0);
  const kcalGoal = goal?.kcal ?? 0;
  const kcalProgress = kcalGoal > 0 ? kcalConsumed / kcalGoal : 0;

  const waterProgress = water && water.goal_ml > 0 ? water.total_ml_today / water.goal_ml : 0;

  const weekStart = startOfWeekIso();
  const workoutsThisWeek = sessions.filter((s) => s.completed_at && s.completed_at >= weekStart).length;
  const lastSleep = sleepLogs[0];

  const firstName = user?.display_name?.split(" ")[0] ?? "";
  const dateLabel = new Date().toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.xl + spacing.md, paddingBottom: spacing.xxl }}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero de boas-vindas */}
        <View
          style={{
            backgroundColor: colors.primary,
            borderRadius: 24,
            padding: spacing.lg,
            marginBottom: spacing.md,
          }}
        >
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
            <Text style={[type.caption, { color: colors.textOnPrimary, opacity: 0.85, textTransform: "capitalize" }]}>
              {dateLabel}
            </Text>
            <View
              style={{
                paddingVertical: 4,
                paddingHorizontal: 12,
                borderRadius: 999,
                backgroundColor: user?.plan === "pro" ? colors.secondary : "rgba(255,255,255,0.18)",
              }}
            >
              <Text style={[type.caption, { color: colors.textOnPrimary, fontWeight: "800" }]}>
                {user?.plan === "pro" ? "★ PRO" : "FREE"}
              </Text>
            </View>
          </View>
          <Text style={[type.h1, { color: colors.textOnPrimary, fontSize: 28, marginTop: 4 }]}>
            {greeting()}, {firstName} 👋
          </Text>
          <Text style={[type.bodySmall, { color: colors.textOnPrimary, opacity: 0.9, marginTop: 2 }]}>
            {motivationOfTheDay()}
          </Text>
        </View>

        {/* Anéis: calorias + água */}
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]}>Hoje</Text>
          <View style={{ flexDirection: "row", justifyContent: "space-around" }}>
            <ProgressRing
              size={130}
              strokeWidth={13}
              progress={kcalProgress}
              value={kcalGoal > 0 ? `${Math.round(kcalConsumed)}` : "—"}
              label={kcalGoal > 0 ? `/ ${Math.round(kcalGoal)} kcal` : "sem meta"}
              color={kcalProgress > 1 ? colors.warning : colors.primary}
            />
            <ProgressRing
              size={130}
              strokeWidth={13}
              progress={waterProgress}
              value={`${((water?.total_ml_today ?? 0) / 1000).toFixed(1)}L`}
              label={`/ ${((water?.goal_ml ?? 0) / 1000).toFixed(1)}L água`}
              color={colors.info}
            />
          </View>
        </Card>

        {/* Cards de módulo */}
        <StatCard
          icon="barbell"
          iconColor={colors.moduleTraining}
          title="Treinos essa semana"
          value={String(workoutsThisWeek)}
          hint={workoutsThisWeek === 0 ? "Bora começar?" : "Mandou bem!"}
          onPress={() => navigation.navigate("Treino")}
        />
        <StatCard
          icon="moon"
          iconColor={colors.moduleSleep}
          title="Última noite de sono"
          value={
            lastSleep
              ? `${Math.floor(lastSleep.duration_minutes / 60)}h${String(lastSleep.duration_minutes % 60).padStart(2, "0")}`
              : "—"
          }
          hint={lastSleep ? `Qualidade ${lastSleep.quality}/5` : "Toque para registrar"}
          onPress={() => navigation.navigate("Sleep")}
        />
        <StatCard
          icon="restaurant"
          iconColor={colors.moduleNutrition}
          title="Refeições registradas hoje"
          value={String(meals.length)}
          hint="Ver diário"
          onPress={() => navigation.navigate("Nutricao")}
        />

        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate("Evolution")}
          style={{ marginTop: spacing.xs }}
        >
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.primaryDark,
              borderRadius: 20,
              padding: spacing.lg,
            }}
          >
            <Ionicons name="trending-up" size={26} color={colors.textOnPrimary} />
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <Text style={[type.h2, { color: colors.textOnPrimary }]}>Sua evolução</Text>
              <Text style={[type.caption, { color: colors.textOnPrimary, opacity: 0.85 }]}>
                Peso, volume e carga ao longo do tempo
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textOnPrimary} />
          </View>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

function StatCard({
  icon,
  iconColor,
  title,
  value,
  hint,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  title: string;
  value: string;
  hint: string;
  onPress: () => void;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <TouchableOpacity activeOpacity={0.7} onPress={onPress} style={{ marginBottom: spacing.md }}>
      <Card>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <View
            style={{
              width: 48,
              height: 48,
              borderRadius: 16,
              backgroundColor: iconColor + "22",
              alignItems: "center",
              justifyContent: "center",
              marginRight: spacing.md,
            }}
          >
            <Ionicons name={icon} size={24} color={iconColor} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.caption, { color: colors.textSecondary }]}>{title}</Text>
            <Text style={[type.h2, { color: colors.textPrimary, fontSize: 22 }]}>{value}</Text>
          </View>
          <View style={{ alignItems: "flex-end" }}>
            <Text style={[type.caption, { color: iconColor, fontWeight: "600" }]}>{hint}</Text>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </View>
        </View>
      </Card>
    </TouchableOpacity>
  );
}
