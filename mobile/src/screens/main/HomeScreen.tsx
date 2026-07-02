import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { useAuth } from "../../context/AuthContext";
import { listSleepLogs, type SleepLog } from "../../api/sleep";
import { getTodayWaterSummary, type WaterSummary } from "../../api/water";
import { listWorkoutSessions, type WorkoutSessionDetail } from "../../api/workoutSessions";
import { useTheme } from "../../theme/ThemeProvider";

function startOfWeekIso(): string {
  const d = new Date();
  const day = d.getDay();
  d.setDate(d.getDate() - day);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

export function HomeScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [water, setWater] = useState<WaterSummary | null>(null);
  const [sleepLogs, setSleepLogs] = useState<SleepLog[]>([]);
  const [sessions, setSessions] = useState<WorkoutSessionDetail[]>([]);

  useFocusEffect(
    useCallback(() => {
      getTodayWaterSummary().then(setWater);
      listSleepLogs().then(setSleepLogs);
      listWorkoutSessions().then(setSessions);
    }, [])
  );

  const lastSleep = sleepLogs[0];
  const weekStart = startOfWeekIso();
  const workoutsThisWeek = sessions.filter(
    (s) => s.completed_at && s.completed_at >= weekStart
  ).length;

  return (
    <ScrollView
      contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}
    >
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
        Olá, {user?.display_name?.split(" ")[0] ?? "tudo bem"}
      </Text>
      <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
        Seu resumo da semana
      </Text>

      <View
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          borderWidth: 1,
          borderColor: colors.border,
          padding: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <SummaryRow
          icon="🏋️"
          label="Treinos concluídos essa semana"
          value={String(workoutsThisWeek)}
        />
        <SummaryRow
          icon="💧"
          label="Água hoje"
          value={`${water?.total_ml_today ?? 0} / ${water?.goal_ml ?? 0} ml`}
        />
        <TouchableOpacity onPress={() => navigation.navigate("Sleep")}>
          <SummaryRow
            icon="😴"
            label="Última noite de sono"
            value={
              lastSleep
                ? `${Math.floor(lastSleep.duration_minutes / 60)}h${lastSleep.duration_minutes % 60}min · nota ${lastSleep.quality}`
                : "Registrar"
            }
          />
        </TouchableOpacity>
      </View>

      <View
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          borderWidth: 1,
          borderColor: colors.border,
          padding: spacing.md,
        }}
      >
        <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
          Plano atual
        </Text>
        <Text style={[type.body, { color: colors.textSecondary }]}>
          {user?.plan === "pro" ? "Pro" : "Free"}
        </Text>
      </View>
    </ScrollView>
  );
}

function SummaryRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "center",
        paddingVertical: spacing.xs,
      }}
    >
      <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
        {icon} {label}
      </Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>{value}</Text>
    </View>
  );
}
