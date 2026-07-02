import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

import { createChallenge, listMyChallenges, type Challenge } from "../../api/challenges";
import { Button } from "../../components/Button";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const METRIC_LABELS: Record<Challenge["metric"], string> = {
  workout_count: "Nº de treinos",
  total_volume: "Volume total",
  streak_days: "Streak de dias",
};

function isoInDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function ChallengesScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState<Challenge["metric"]>("workout_count");
  const [invite, setInvite] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      listMyChallenges().then(setChallenges);
    }, [])
  );

  async function handleCreate() {
    if (!name.trim()) {
      Alert.alert("Dê um nome ao desafio");
      return;
    }
    setIsSubmitting(true);
    try {
      await createChallenge({
        name: name.trim(),
        metric,
        start_date: isoInDays(0),
        end_date: isoInDays(30),
        invite_handles: invite
          .split(",")
          .map((h) => h.trim().toLowerCase())
          .filter(Boolean),
      });
      setName("");
      setInvite("");
      listMyChallenges().then(setChallenges);
    } catch (err: any) {
      Alert.alert("Não foi possível criar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>Desafios</Text>

      <FlatList
        data={challenges}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => navigation.navigate("ChallengeDetail", { challengeId: item.id })}
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: colors.border,
              padding: spacing.md,
              marginBottom: spacing.sm,
            }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{item.name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {METRIC_LABELS[item.metric]} · até {item.end_date}
            </Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
            Nenhum desafio ainda.
          </Text>
        }
      />

      <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
        Criar novo desafio (30 dias)
      </Text>
      <TextInput
        value={name}
        onChangeText={setName}
        placeholder="Nome do desafio"
        placeholderTextColor={colors.textSecondary}
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            height: 44,
            paddingHorizontal: spacing.md,
            marginBottom: spacing.sm,
          },
        ]}
      />
      {(Object.keys(METRIC_LABELS) as Challenge["metric"][]).map((m) => (
        <OptionButton key={m} label={METRIC_LABELS[m]} selected={metric === m} onPress={() => setMetric(m)} />
      ))}
      <TextInput
        value={invite}
        onChangeText={setInvite}
        placeholder="Convidar @handles separados por vírgula"
        placeholderTextColor={colors.textSecondary}
        autoCapitalize="none"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            height: 44,
            paddingHorizontal: spacing.md,
            marginVertical: spacing.sm,
          },
        ]}
      />
      <Button title="Criar desafio" onPress={handleCreate} loading={isSubmitting} />
    </View>
  );
}
