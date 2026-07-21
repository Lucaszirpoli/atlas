import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  getCoachingAnalysis,
  type CoachingAnalysis,
  type CoachingFinding,
  type CoachingMetrics,
} from "../../api/coaching";
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

  const [analysis, setAnalysis] = useState<CoachingAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  // Recarrega a cada foco: a pessoa registra peso/refeição e volta pra ver o
  // que mudou. Só pro Pro — o Free nem chega aqui (paywall abaixo).
  useFocusEffect(
    useCallback(() => {
      if (!isPro) return;
      let vivo = true;
      setErro(false);
      getCoachingAnalysis()
        .then((a) => vivo && setAnalysis(a))
        .catch(() => vivo && setErro(true))
        .finally(() => vivo && setLoading(false));
      return () => {
        vivo = false;
      };
    }, [isPro])
  );

  if (!isPro) {
    return <CoachingPaywall />;
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
      {/* Análise da semana — o motor determinístico (sem IA) lê os registros. */}
      {loading && !analysis ? (
        <Card style={{ marginBottom: spacing.md, alignItems: "center", paddingVertical: spacing.xl }}>
          <ActivityIndicator color={colors.primary} />
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            Lendo seus registros...
          </Text>
        </Card>
      ) : erro ? (
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.body, { color: colors.textPrimary }]}>Não consegui carregar sua análise agora.</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4 }]}>
            Puxe pra atualizar ou tente de novo em instantes.
          </Text>
        </Card>
      ) : analysis ? (
        <AnalysisView analysis={analysis} />
      ) : null}

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

function AnalysisView({ analysis }: { analysis: CoachingAnalysis }) {
  const { colors, type, spacing, radius } = useTheme();
  const m = analysis.metrics;

  return (
    <>
      {/* Manchete + confiança */}
      <Card style={{ marginBottom: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.xs }}>
          <Ionicons name="compass" size={22} color={colors.primary} />
          <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>Seu Coaching</Text>
          <View
            style={{
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.pill,
              paddingVertical: 3,
              paddingHorizontal: 9,
            }}
          >
            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>
              {analysis.window_days} dias
            </Text>
          </View>
        </View>
        <Text style={[type.body, { color: colors.textPrimary, lineHeight: 22 }]}>{analysis.headline}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 6 }]}>
          Análise por regras dos seus registros — confiança {analysis.confidence}.
        </Text>
      </Card>

      {/* Métricas destiladas (só quando há dado que sustente) */}
      {analysis.has_enough_data ? <MetricStrip m={m} /> : null}

      {/* Achados com ajuste proposto */}
      {analysis.findings.map((f) => (
        <FindingCard key={f.key} f={f} />
      ))}

      {/* Lacunas de dado — o que registrar pra afinar a análise */}
      {analysis.data_gaps.length > 0 ? (
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", marginBottom: spacing.xs }]}>
            {analysis.has_enough_data ? "Pra afinar a análise" : "Me dê um pouco mais pra trabalhar"}
          </Text>
          {analysis.data_gaps.map((g, i) => (
            <View key={i} style={{ flexDirection: "row", gap: 8, marginTop: 6 }}>
              <Ionicons name="ellipse" size={7} color={colors.primary} style={{ marginTop: 7 }} />
              <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1, lineHeight: 19 }]}>{g}</Text>
            </View>
          ))}
        </Card>
      ) : null}
    </>
  );
}

function MetricStrip({ m }: { m: CoachingMetrics }) {
  const { colors, type, spacing, radius } = useTheme();

  const trend =
    m.weight_trend_kg_per_week != null
      ? `${m.weight_trend_kg_per_week > 0 ? "+" : ""}${m.weight_trend_kg_per_week.toFixed(2)} kg/sem`
      : "—";
  const kcal = m.avg_kcal != null ? `${m.avg_kcal}` : "—";
  const kcalSub = m.goal_kcal != null ? `meta ${Math.round(m.goal_kcal)}` : "sem meta";
  const prot = m.avg_protein_g != null ? `${Math.round(m.avg_protein_g)} g` : "—";
  const protSub = m.protein_target_g != null ? `alvo ${Math.round(m.protein_target_g)} g` : "proteína";
  const treino = m.sessions_per_week != null ? `${m.sessions_per_week.toFixed(1)}` : "—";
  const sono = m.avg_sleep_hours != null ? `${m.avg_sleep_hours.toFixed(1)} h` : "—";

  const tiles = [
    { label: "Peso (tendência)", value: trend, sub: m.weight_points ? `${m.weight_points} registros` : "registre o peso" },
    { label: "Calorias/dia", value: kcal, sub: kcalSub },
    { label: "Proteína/dia", value: prot, sub: protSub },
    { label: "Treinos/semana", value: treino, sub: "concluídos" },
    { label: "Sono", value: sono, sub: "por noite" },
  ];

  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md }}>
      {tiles.map((t) => (
        <View
          key={t.label}
          style={{
            width: "47.5%",
            backgroundColor: colors.surface,
            borderRadius: radius.button,
            padding: spacing.md,
          }}
        >
          <Text style={[type.caption, { color: colors.textSecondary }]}>{t.label}</Text>
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 20, marginTop: 2 }]}>{t.value}</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>{t.sub}</Text>
        </View>
      ))}
    </View>
  );
}

function FindingCard({ f }: { f: CoachingFinding }) {
  const { colors, type, spacing, radius } = useTheme();
  const tint =
    f.severity === "action" ? colors.primary : f.severity === "attention" ? colors.warning : colors.success;
  const icon =
    f.severity === "action" ? "flash" : f.severity === "attention" ? "alert-circle" : "checkmark-circle";

  return (
    <Card accent={tint} style={{ marginBottom: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Ionicons name={icon as keyof typeof Ionicons.glyphMap} size={18} color={tint} />
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>{f.title}</Text>
      </View>
      <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 20 }]}>{f.detail}</Text>
      {f.proposal ? (
        <View
          style={{
            marginTop: spacing.sm,
            padding: spacing.sm,
            borderRadius: radius.button,
            backgroundColor: tint + "14",
            borderWidth: 1,
            borderColor: tint + "33",
          }}
        >
          <Text style={[type.caption, { color: tint, fontWeight: "700", marginBottom: 2 }]}>Sugestão</Text>
          <Text style={[type.bodySmall, { color: colors.textPrimary, lineHeight: 20 }]}>{f.proposal}</Text>
        </View>
      ) : null}
    </Card>
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
