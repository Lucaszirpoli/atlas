import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { createChallenge, listMyChallenges, type Challenge } from "../../api/challenges";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const METRIC_META: Record<Challenge["metric"], { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  workout_count: { label: "Nº de treinos", icon: "checkbox" },
  total_volume: { label: "Volume total", icon: "barbell" },
  streak_days: { label: "Streak de dias", icon: "flame" },
  // Conta check-ins com prova de localização na academia (ver GymScreen).
  gym_checkin: { label: "Idas à academia", icon: "location" },
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
          .map((h) => h.trim().toLowerCase().replace(/^@/, ""))
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
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Academia + check-in: base do desafio "quem vai mais à academia". */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("Gym")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          borderRadius: radius.card,
          padding: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <Ionicons name="location" size={22} color={colors.moduleSocial} />
        <View style={{ flex: 1, marginLeft: spacing.sm }}>
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>Minha academia</Text>
          <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
            Check-in com localização — sua presença nos desafios
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </TouchableOpacity>

      {challenges.length > 0 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Meus desafios
          </Text>
          {challenges.map((item) => (
            <TouchableOpacity
              key={item.id}
              activeOpacity={0.8}
              onPress={() => navigation.navigate("ChallengeDetail", { challengeId: item.id })}
            >
              <Card accent={colors.moduleSocial} style={{ marginBottom: spacing.sm }}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <View
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: 14,
                      backgroundColor: colors.moduleSocial + "1E",
                      alignItems: "center",
                      justifyContent: "center",
                      marginRight: spacing.sm,
                    }}
                  >
                    <Ionicons name={METRIC_META[item.metric].icon} size={20} color={colors.moduleSocial} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{item.name}</Text>
                    <Text style={[type.caption, { color: colors.textSecondary }]}>
                      {METRIC_META[item.metric].label} · até{" "}
                      {new Date(item.end_date + "T00:00:00").toLocaleDateString("pt-BR")}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
                </View>
              </Card>
            </TouchableOpacity>
          ))}
        </>
      ) : null}

      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.md, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Criar desafio (30 dias)
      </Text>
      <Card>
        {/* Placeholders curtos + numberOfLines=1: os longos quebravam em duas
            linhas dentro da altura fixa e apareciam cortados no meio. */}
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Nome do desafio"
          placeholderTextColor={colors.textSecondary}
          numberOfLines={1}
          style={[
            type.body,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              height: 50,
              paddingHorizontal: spacing.md,
              marginBottom: spacing.sm,
            },
          ]}
        />
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
          Ex: "Quem treina mais em julho"
        </Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
          Como vamos medir?
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
          {(Object.keys(METRIC_META) as Challenge["metric"][]).map((m) => (
            <OptionButton
              key={m}
              compact
              label={METRIC_META[m].label}
              selected={metric === m}
              onPress={() => setMetric(m)}
            />
          ))}
        </View>
        {metric === "gym_checkin" ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
            Cada pessoa cadastra a academia dela e faz check-in estando lá — a localização é a prova de presença.
          </Text>
        ) : null}
        <TextInput
          value={invite}
          onChangeText={setInvite}
          placeholder="Convidar amigos"
          placeholderTextColor={colors.textSecondary}
          autoCapitalize="none"
          numberOfLines={1}
          style={[
            type.body,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              height: 50,
              paddingHorizontal: spacing.md,
              marginTop: spacing.md,
            },
          ]}
        />
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, marginBottom: spacing.md }]}>
          Separe por vírgula: @joao, @maria
        </Text>
        <Button title="Criar desafio" icon="🏆" onPress={handleCreate} loading={isSubmitting} />
      </Card>
    </ScrollView>
  );
}
