import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useRef, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  applyDietAdjustment,
  applyTechnique,
  getCoachingAnalysis,
  listCoachingAdjustments,
  revertAdjustment,
  type CoachingAdjustment,
  type CoachingAnalysis,
  type CoachingChart,
  type CoachingInsight,
} from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { CoachingProgress } from "./CoachingProgress";

// Períodos de análise/gráfico. "Semanal" = a análise da semana atual (como foi
// x como deveria ter sido); depois 4/8/12 semanas.
const PERIODS: { label: string; days: number }[] = [
  { label: "Semanal", days: 7 },
  { label: "4 sem", days: 28 },
  { label: "8 sem", days: 56 },
  { label: "12 sem", days: 84 },
];

// "2026-07-21T..." -> "21/07"
function formatDia(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

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
  const [chartMetric, setChartMetric] = useState<CoachingChart>("peso");
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const chartY = useRef(0);

  // Toque no quadradinho de gráfico de uma barra: troca a métrica do gráfico e
  // rola até ele (o gráfico fica logo abaixo das barras).
  const onOpenChart = useCallback((chart: CoachingChart) => {
    setChartMetric(chart);
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ y: Math.max(0, chartY.current - 12), animated: true })
    );
  }, []);

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
      ref={scrollRef}
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
        <AnalysisView analysis={analysis} onApplied={onApplied} onOpenChart={onOpenChart} />
      ) : null}

      {/* Pergunte ao coach — a IA que EXPLICA a análise (não muda plano). */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("CoachChat")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: spacing.md,
          backgroundColor: colors.primary + "14",
          borderWidth: 1,
          borderColor: colors.primary + "33",
          borderRadius: radius.card,
          padding: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <View
          style={{
            width: 42,
            height: 42,
            borderRadius: 14,
            backgroundColor: colors.primary + "22",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="chatbubbles" size={22} color={colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>Pergunte ao coach</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
            Tire dúvidas sobre sua análise, treino, dieta e sono
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.primary} />
      </TouchableOpacity>

      {/* Gráfico simples do período — UM de cada vez, controlado pelas barras
          (o quadradinho de gráfico troca a métrica). Absorve a Evolução. */}
      <View onLayout={(e) => (chartY.current = e.nativeEvent.layout.y)}>
        <CoachingProgress
          periodDays={periodDays}
          metric={chartMetric}
          onMetricChange={setChartMetric}
          onDataChanged={load}
        />
      </View>

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
  onOpenChart,
}: {
  analysis: CoachingAnalysis;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();

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
        {analysis.metrics.baseline_at ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 8 }}>
            <Ionicons name="flag" size={13} color={colors.primary} />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>
              Análise recomeçada em {formatDia(analysis.metrics.baseline_at)} (troca de objetivo) — o histórico
              completo segue nos gráficos.
            </Text>
          </View>
        ) : null}
      </Card>

      {/* Barras por dimensão — cada uma compara com o esperado PRO OBJETIVO,
          com atalho pro gráfico daquela info. Substituem os antigos tiles. */}
      {analysis.insights.map((ins) => (
        <InsightBar key={ins.key} ins={ins} onApplied={onApplied} onOpenChart={onOpenChart} />
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

// Barra horizontal por dimensão (peso/calorias/macros/sono/carga/treino).
// Explica o status vs objetivo; se houver ajuste, mostra "Aplicar"; e traz um
// quadradinho de gráfico que abre o gráfico daquela info.
function InsightBar({
  ins,
  onApplied,
  onOpenChart,
}: {
  ins: CoachingInsight;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [applying, setApplying] = useState(false);
  const [aplicado, setAplicado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const tint =
    ins.severity === "action" ? colors.primary : ins.severity === "attention" ? colors.warning : colors.success;

  const delta = ins.adjustment?.kcal_delta;
  const podeAplicarDieta = typeof delta === "number" && delta !== 0 && !!ins.finding_key;

  const tecnica = ins.adjustment?.technique_label;
  const podeAplicarTecnica = !!ins.adjustment?.technique && !!ins.finding_key;

  async function aplicar() {
    if (!ins.finding_key) return;
    setErro(null);
    setApplying(true);
    try {
      const r = await applyDietAdjustment(ins.finding_key);
      onApplied("Meta ajustada", r.message);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui aplicar agora."));
    } finally {
      setApplying(false);
    }
  }

  async function aplicarTec() {
    if (!ins.finding_key) return;
    setErro(null);
    setApplying(true);
    try {
      const r = await applyTechnique(ins.finding_key);
      setAplicado(true);
      onApplied("Técnica aplicada", r.message);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui aplicar agora."));
    } finally {
      setApplying(false);
    }
  }

  return (
    <Card accent={tint} style={{ marginBottom: spacing.sm }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: tint }} />
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>{ins.title}</Text>
        {/* Quadradinho de gráfico — abre o gráfico dessa dimensão. */}
        {ins.chart ? (
          <TouchableOpacity
            onPress={() => onOpenChart(ins.chart as CoachingChart)}
            hitSlop={8}
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              backgroundColor: colors.surfaceAlt,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Ionicons name="stats-chart" size={15} color={colors.textSecondary} />
          </TouchableOpacity>
        ) : null}
      </View>
      <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 20 }]}>{ins.detail}</Text>

      {podeAplicarDieta ? (
        <View style={{ marginTop: spacing.sm }}>
          <Button
            title={applying ? "Aplicando..." : `Aplicar ajuste (${delta! > 0 ? "+" : ""}${delta} kcal)`}
            variant="secondary"
            compact
            loading={applying}
            onPress={aplicar}
          />
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
            Cria uma nova versão da sua meta. Dá pra desfazer depois.
          </Text>
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: 4, textAlign: "center" }]}>{erro}</Text>
          ) : null}
        </View>
      ) : podeAplicarTecnica ? (
        <View style={{ marginTop: spacing.sm }}>
          {aplicado ? (
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 }}>
              <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>
                Aplicado — aparece na prévia do treino
              </Text>
            </View>
          ) : (
            <>
              <Button
                title={applying ? "Aplicando..." : `Aplicar ${tecnica} no treino`}
                variant="secondary"
                compact
                loading={applying}
                onPress={aplicarTec}
              />
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
                Vira uma dica na prévia do treino. Dá pra remover lá.
              </Text>
            </>
          )}
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
