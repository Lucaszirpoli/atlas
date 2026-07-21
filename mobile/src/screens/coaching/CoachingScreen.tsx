import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  applyDietAdjustment,
  getCoachingAnalysis,
  listCoachingAdjustments,
  revertAdjustment,
  type CoachingAdjustment,
  type CoachingAnalysis,
  type CoachingFinding,
  type CoachingMetrics,
} from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { CoachingProgress } from "./CoachingProgress";

// Períodos de análise/gráfico — 4/8/12 semanas.
const PERIODS: { label: string; days: number }[] = [
  { label: "4 sem", days: 28 },
  { label: "8 sem", days: 56 },
  { label: "12 sem", days: 84 },
];

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
  const [adjustments, setAdjustments] = useState<CoachingAdjustment[]>([]);
  const [periodDays, setPeriodDays] = useState(28);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);

  const load = useCallback(() => {
    if (!isPro) return Promise.resolve();
    setErro(false);
    return Promise.all([
      getCoachingAnalysis(periodDays).then(setAnalysis),
      listCoachingAdjustments()
        .then(setAdjustments)
        .catch(() => {}), // histórico é secundário; não derruba a tela
    ])
      .catch(() => setErro(true))
      .finally(() => setLoading(false));
  }, [isPro, periodDays]);

  // Recarrega a cada foco: a pessoa registra peso/refeição e volta pra ver o
  // que mudou. Só pro Pro — o Free nem chega aqui (paywall abaixo).
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onApplied = useCallback(
    (title: string, message: string) => {
      setAviso({ title, message });
      load(); // a análise muda depois do ajuste — recarrega
    },
    [load]
  );

  if (!isPro) {
    return <CoachingPaywall />;
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
      {/* Período da análise e dos gráficos — controla a janela inteira. */}
      <View style={{ flexDirection: "row", gap: spacing.xs, marginBottom: spacing.md }}>
        {PERIODS.map((p) => {
          const on = periodDays === p.days;
          return (
            <TouchableOpacity
              key={p.days}
              onPress={() => setPeriodDays(p.days)}
              style={{
                flex: 1,
                alignItems: "center",
                backgroundColor: on ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: on ? colors.primary : colors.border,
                borderRadius: radius.pill,
                paddingVertical: 8,
              }}
            >
              <Text
                style={[
                  type.caption,
                  { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: on ? "700" : "500" },
                ]}
              >
                {p.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Análise do período — o motor determinístico (sem IA) lê os registros. */}
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
        <AnalysisView analysis={analysis} onApplied={onApplied} />
      ) : null}

      {/* Gráfico simples do período — UM de cada vez (peso/calorias/treino),
          com registro de peso ali mesmo. Absorve a antiga tela de Evolução. */}
      <CoachingProgress periodDays={periodDays} onDataChanged={load} />

      {/* Ajustes que a pessoa aplicou — com Desfazer. */}
      {adjustments.length > 0 ? (
        <AdjustmentsSection
          adjustments={adjustments}
          onReverted={(msg) => onApplied("Ajuste desfeito", msg)}
        />
      ) : null}

      {/* Módulos pessoais que passaram a viver dentro do Coaching. */}
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
        Seus dados e análises
      </Text>

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

      <InfoDialog
        visible={aviso != null}
        onClose={() => setAviso(null)}
        title={aviso?.title ?? ""}
        message={aviso?.message}
      />
    </ScrollView>
  );
}

function AnalysisView({
  analysis,
  onApplied,
}: {
  analysis: CoachingAnalysis;
  onApplied: (title: string, message: string) => void;
}) {
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
        <FindingCard key={f.key} f={f} onApplied={onApplied} />
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

function FindingCard({
  f,
  onApplied,
}: {
  f: CoachingFinding;
  onApplied: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [applying, setApplying] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const tint =
    f.severity === "action" ? colors.primary : f.severity === "attention" ? colors.warning : colors.success;
  const icon =
    f.severity === "action" ? "flash" : f.severity === "attention" ? "alert-circle" : "checkmark-circle";

  // Ajuste aplicável em 1 toque (só nos achados de caloria). Muda a meta de
  // verdade — por isso pede confirmação antes.
  const podeAplicar = typeof f.adjustment?.kcal_delta === "number" && f.adjustment.kcal_delta !== 0;

  async function aplicar() {
    setErro(null);
    setApplying(true);
    try {
      const r = await applyDietAdjustment(f.key);
      onApplied("Meta ajustada", r.message);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui aplicar agora."));
    } finally {
      setApplying(false);
    }
  }

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

      {podeAplicar ? (
        <View style={{ marginTop: spacing.sm }}>
          <Button
            title={
              applying
                ? "Aplicando..."
                : `Aplicar ajuste (${f.adjustment!.kcal_delta! > 0 ? "+" : ""}${f.adjustment!.kcal_delta} kcal)`
            }
            variant="secondary"
            compact
            loading={applying}
            onPress={aplicar}
          />
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
            Cria uma nova versão da sua meta. Você pode mudar quando quiser em Objetivo e metas.
          </Text>
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: 4, textAlign: "center" }]}>{erro}</Text>
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

function AdjustmentsSection({
  adjustments,
  onReverted,
}: {
  adjustments: CoachingAdjustment[];
  onReverted: (message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [revertingId, setRevertingId] = useState<number | null>(null);

  async function desfazer(id: number) {
    setRevertingId(id);
    try {
      const r = await revertAdjustment(id);
      onReverted(r.message);
    } catch {
      // silencioso — a lista recarrega no próximo foco
    } finally {
      setRevertingId(null);
    }
  }

  function quando(iso: string): string {
    const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
    if (dias <= 0) return "hoje";
    if (dias === 1) return "ontem";
    return `há ${dias} dias`;
  }

  return (
    <>
      <Text
        style={[
          type.caption,
          { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm },
        ]}
      >
        Ajustes que você aplicou
      </Text>
      <Card style={{ marginBottom: spacing.md }}>
        {adjustments.map((a, i) => {
          const revertido = a.reverted_at != null;
          return (
            <View
              key={a.id}
              style={{
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: spacing.sm,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.border,
              }}
            >
              <View style={{ flex: 1 }}>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
                  Meta {a.kcal_delta > 0 ? "+" : ""}
                  {Math.round(a.kcal_delta)} kcal ({Math.round(a.prev_kcal)} → {Math.round(a.new_kcal)})
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                  {quando(a.created_at)}
                  {revertido ? " · desfeito" : ""}
                </Text>
              </View>
              {revertido ? (
                <Ionicons name="arrow-undo" size={16} color={colors.textSecondary} />
              ) : (
                <TouchableOpacity
                  onPress={() => desfazer(a.id)}
                  disabled={revertingId === a.id}
                  style={{
                    borderWidth: 1,
                    borderColor: colors.border,
                    borderRadius: radius.pill,
                    paddingVertical: 5,
                    paddingHorizontal: 12,
                    opacity: revertingId === a.id ? 0.5 : 1,
                  }}
                >
                  <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700" }]}>
                    {revertingId === a.id ? "..." : "Desfazer"}
                  </Text>
                </TouchableOpacity>
              )}
            </View>
          );
        })}
      </Card>
    </>
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
