import { useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { getLeaderboard, type Challenge, type LeaderboardEntry } from "../../api/challenges";
import { useTheme } from "../../theme/ThemeProvider";

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

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.sm }]}>{challenge.name}</Text>
      <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
        {challenge.start_date} até {challenge.end_date}
      </Text>

      {entries.map((entry, index) => (
        <View
          key={entry.user.id}
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            paddingVertical: spacing.sm,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
          }}
        >
          <Text style={[type.body, { color: colors.textPrimary }]}>
            {index + 1}º {entry.user.display_name}
          </Text>
          <Text style={[type.body, { color: colors.textSecondary }]}>{Math.round(entry.value * 10) / 10}</Text>
        </View>
      ))}
    </View>
  );
}
