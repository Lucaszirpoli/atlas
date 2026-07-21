import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

/**
 * Coaching — a área-diferencial do plano Pro. Reúne objetivo, metas, medidas,
 * evolução, dieta, treino e sono num acompanhamento contínuo.
 *
 * FASE 1 (esta tela): o gate Pro, a APRESENTAÇÃO pro Free, e a CASA das análises
 * pessoais que saíram das outras abas (Evolução, Medidas, Objetivo). O motor
 * determinístico (métricas → detecção → diagnóstico → políticas) que gera as
 * recomendações semanais é a Fase 2 — aqui ele aparece como "em construção" de
 * forma honesta, em vez de mostrar um resumo falso.
 */
export function CoachingScreen() {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  if (!isPro) {
    return <CoachingPaywall />;
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
      {/* Estado atual — a análise semanal do motor entra aqui na Fase 2. */}
      <Card style={{ marginBottom: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.sm }}>
          <Ionicons name="compass" size={22} color={colors.primary} />
          <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>Seu Coaching</Text>
        </View>
        <Text style={[type.body, { color: colors.textSecondary, lineHeight: 22 }]}>
          Acompanhamento contínuo que cruza treino, dieta, sono e evolução para propor ajustes graduais —
          sempre com o seu aval antes de mudar qualquer plano.
        </Text>
        <View
          style={{
            marginTop: spacing.md,
            padding: spacing.md,
            borderRadius: radius.button,
            backgroundColor: colors.primary + "12",
            borderWidth: 1,
            borderColor: colors.primary + "33",
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <Ionicons name="construct" size={16} color={colors.primary} />
            <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]}>
              Análise da semana — em construção
            </Text>
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, lineHeight: 18 }]}>
            O motor que lê seus registros (peso, adesão, desempenho, sono) e sugere ajustes com base em
            regras — sem inventar — está sendo montado. Enquanto isso, use os módulos abaixo.
          </Text>
        </View>
      </Card>

      {/* Módulos pessoais que passaram a viver dentro do Coaching. */}
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
        Seus dados e análises
      </Text>

      <CoachRow
        icon="trending-up"
        tint={colors.moduleTraining}
        title="Evolução"
        subtitle="Gráficos de peso, treino, sono e dieta"
        onPress={() => navigation.navigate("Evolution", { initialMetrics: ["treino", "sono", "dieta"] })}
      />
      <CoachRow
        icon="flag"
        tint={colors.moduleNutrition}
        title="Objetivo e metas"
        subtitle="Seu objetivo e a meta de calorias/macros"
        onPress={() => navigation.navigate("NutritionModule", { screen: "GoalSettings" })}
      />
      <CoachRow
        icon="body"
        tint={colors.info}
        title="Medidas e fotos"
        subtitle="Circunferências e fotos de progresso"
        onPress={() => navigation.navigate("NutritionModule", { screen: "Measurements" })}
      />
    </ScrollView>
  );
}

function CoachRow({
  icon,
  tint,
  title,
  subtitle,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  tint: string;
  title: string;
  subtitle: string;
  onPress: () => void;
}) {
  const { colors, type, spacing, radius, shadow } = useTheme();
  return (
    <TouchableOpacity activeOpacity={0.8} onPress={onPress} style={{ marginBottom: spacing.sm }}>
      <View
        style={[
          {
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.surface,
            borderRadius: radius.button,
            padding: spacing.md,
          },
          shadow.sm,
        ]}
      >
        <View
          style={{
            width: 42,
            height: 42,
            borderRadius: 13,
            backgroundColor: tint + "22",
            alignItems: "center",
            justifyContent: "center",
            marginRight: spacing.md,
          }}
        >
          <Ionicons name={icon} size={22} color={tint} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{title}</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>{subtitle}</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
      </View>
    </TouchableOpacity>
  );
}

/** Free: apresentação do Coaching + assinar. Nunca dá acesso parcial aos dados
 * internos (spec §2). */
function CoachingPaywall() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const beneficios = [
    ["compass", "Acompanhamento contínuo", "O app aprende sua rotina e ajusta treino e dieta ao longo do tempo."],
    ["barbell", "Treino que evolui com você", "Volume, progressão e trocas de exercício com base no seu desempenho e recuperação."],
    ["restaurant", "Dieta que se adapta", "Calorias e macros ajustados pela tendência do seu peso e adesão — não por chute."],
    ["moon", "Sono e recuperação", "Cruza seu sono com o treino e evita ajustes bruscos quando você não recuperou."],
    ["trending-up", "Evolução, metas e medidas", "Tudo num lugar só, com análises e o histórico completo."],
  ] as const;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
      <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
        <View
          style={{
            width: 72,
            height: 72,
            borderRadius: 22,
            backgroundColor: colors.primary + "22",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: spacing.md,
          }}
        >
          <Ionicons name="compass" size={38} color={colors.primary} />
        </View>
        <Text style={[type.h1, { color: colors.textPrimary, textAlign: "center" }]}>Coaching é do Pro</Text>
        <Text style={[type.body, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.xs, maxWidth: 320 }]}>
          Seu acompanhamento pessoal: analisa seus dados e propõe ajustes graduais, sempre com o seu aval.
        </Text>
      </View>

      {beneficios.map(([icon, titulo, texto]) => (
        <View key={titulo} style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
          <View
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              backgroundColor: colors.primary + "18",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Ionicons name={icon as keyof typeof Ionicons.glyphMap} size={20} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{titulo}</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 18 }]}>{texto}</Text>
          </View>
        </View>
      ))}

      <View style={{ marginTop: spacing.md }}>
        <Button title="Assinar o Pro" onPress={() => navigation.navigate("Paywall")} />
      </View>
      <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.md, lineHeight: 18 }]}>
        No plano Free você continua registrando calorias e água, usando as dietas prontas, montando até 3 rotinas
        e os 10 métodos de treino.
      </Text>
    </ScrollView>
  );
}
