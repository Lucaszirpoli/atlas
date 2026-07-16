import { useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { getLeaderboard, type Challenge, type LeaderboardEntry } from "../../api/challenges";
import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";

const MEDALS = ["🥇", "🥈", "🥉"];

/** Mostra o placar na unidade certa de cada tipo — sem isso, "2.5" (que é 2,5%
 * do peso) ou "156374" (que são kg de carga) apareciam como números soltos. */
function formatValue(metric: Challenge["metric"], value: number): string {
  const n = Math.round(value * 10) / 10;
  switch (metric) {
    case "weight_loss_percent":
      return `${n.toLocaleString("pt-BR")}%`;
    case "total_volume":
      return `${Math.round(value).toLocaleString("pt-BR")} kg`;
    case "workout_count":
      return `${Math.round(value)} ${Math.round(value) === 1 ? "treino" : "treinos"}`;
    case "pr_count":
      return `${Math.round(value)} ${Math.round(value) === 1 ? "recorde" : "recordes"}`;
    case "streak_days":
    case "gym_checkin":
    case "sleep_nights":
    case "water_goal_days":
    case "protein_goal_days":
    case "diet_logged_days":
      return `${Math.round(value)} ${Math.round(value) === 1 ? "dia" : "dias"}`;
    default:
      return String(n);
  }
}

export function ChallengeDetailScreen() {
  const { colors, type, spacing } = useTheme();
  const route = useRoute<any>();
  const { challengeId } = route.params;

  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);

  useEffect(() => {
    getLeaderboard(challengeId).then((data) => {
      setChallenge(data.challenge);
      setEntries(data.entries);
    });
  }, [challengeId]);

  if (!challenge) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;

  const maxValue = Math.max(...entries.map((e) => e.value), 1);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Text style={[type.h1, { color: colors.textPrimary }]}>{challenge.name}</Text>
      <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
        {new Date(challenge.start_date + "T00:00:00").toLocaleDateString("pt-BR")} até{" "}
        {new Date(challenge.end_date + "T00:00:00").toLocaleDateString("pt-BR")}
      </Text>

      <Card padded={false}>
        {entries.map((entry, index) => (
          <View
            key={entry.user.id}
            style={{
              flexDirection: "row",
              alignItems: "center",
              padding: spacing.md,
              borderTopWidth: index === 0 ? 0 : 1,
              borderTopColor: colors.border,
            }}
          >
            <Text style={{ fontSize: 20, width: 32 }}>{MEDALS[index] ?? `${index + 1}º`}</Text>
            <Avatar name={entry.user.display_name} handle={entry.user.handle} size={38} />
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: index === 0 ? "800" : "600" }]}>
                {entry.user.display_name}
              </Text>
              <View style={{ height: 6, backgroundColor: colors.surfaceAlt, borderRadius: 3, marginTop: 4 }}>
                <View
                  style={{
                    height: 6,
                    width: `${(entry.value / maxValue) * 100}%`,
                    backgroundColor: index === 0 ? colors.secondary : colors.moduleSocial,
                    borderRadius: 3,
                  }}
                />
              </View>
            </View>
            <Text
              numberOfLines={1}
              style={[
                type.h2,
                { color: index === 0 ? colors.secondary : colors.textPrimary, marginLeft: spacing.sm, fontSize: 15 },
              ]}
            >
              {formatValue(challenge.metric, entry.value)}
            </Text>
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}
