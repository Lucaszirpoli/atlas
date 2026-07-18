import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { createChallenge, listMyChallenges, type Challenge } from "../../api/challenges";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

const METRIC_META: Record<
  Challenge["metric"],
  { label: string; icon: keyof typeof Ionicons.glyphMap; hint: string }
> = {
  workout_count: { label: "Nº de treinos", icon: "checkbox", hint: "Quem treinar mais vezes no período vence." },
  total_volume: {
    label: "Carga total",
    icon: "barbell",
    hint: "Soma de peso × reps das séries válidas (aquecimento e preparatória não contam).",
  },
  pr_count: { label: "Recordes", icon: "trophy", hint: "Quem bater mais recordes pessoais de carga vence." },
  streak_days: { label: "Sequência de dias", icon: "flame", hint: "A maior sequência de dias seguidos treinando." },
  gym_checkin: {
    label: "Idas à academia",
    icon: "location",
    hint: "Cada um cadastra a academia e faz check-in estando lá — a localização é a prova de presença.",
  },
  sleep_nights: { label: "Noites bem dormidas", icon: "moon", hint: "Quantas noites com 7h ou mais de sono." },
  water_goal_days: { label: "Dias batendo a água", icon: "water", hint: "Dias em que bateu a meta de água." },
  protein_goal_days: {
    label: "Dias batendo proteína",
    icon: "nutrition",
    hint: "Dias em que atingiu sua meta de proteína.",
  },
  diet_logged_days: {
    label: "Dias com dieta anotada",
    icon: "restaurant",
    hint: "Dias em que registrou a alimentação — vale a constância, não a restrição.",
  },
  weight_loss_percent: {
    label: "% de peso perdido",
    icon: "trending-down",
    hint: "Quem perder a maior porcentagem do próprio peso. É em % (não kg) porque quem pesa mais perde kg mais rápido. Precisa se pesar no começo e no fim.",
  },
};

// Agrupado por módulo: 9 opções soltas viram uma sopa de chips.
const METRIC_GROUPS: { title: string; metrics: Challenge["metric"][] }[] = [
  { title: "Treino", metrics: ["workout_count", "total_volume", "pr_count"] },
  { title: "Consistência", metrics: ["streak_days", "gym_checkin"] },
  { title: "Saúde", metrics: ["sleep_nights", "water_goal_days"] },
  { title: "Dieta", metrics: ["protein_goal_days", "diet_logged_days"] },
  { title: "Peso", metrics: ["weight_loss_percent"] },
];

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
      Alert.alert("Não foi possível criar", mensagemDeErro(err, "Tente novamente."));
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
        {METRIC_GROUPS.map((group) => (
          <View key={group.title} style={{ marginBottom: spacing.sm }}>
            <Text
              style={[
                type.caption,
                { color: colors.textSecondary, fontWeight: "700", fontSize: 11, marginBottom: 4 },
              ]}
            >
              {group.title.toUpperCase()}
            </Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
              {group.metrics.map((m) => (
                <OptionButton
                  key={m}
                  compact
                  label={METRIC_META[m].label}
                  selected={metric === m}
                  onPress={() => setMetric(m)}
                />
              ))}
            </View>
          </View>
        ))}
        {/* Explica em uma linha o que o tipo escolhido mede. */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-start",
            gap: 6,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            padding: spacing.sm,
          }}
        >
          <Ionicons name={METRIC_META[metric].icon} size={15} color={colors.moduleSocial} style={{ marginTop: 1 }} />
          <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>{METRIC_META[metric].hint}</Text>
        </View>
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
