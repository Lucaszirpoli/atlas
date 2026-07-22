import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import {
  applyCoachAction,
  applyDietAdjustment,
  applyTechnique,
  applyTransitionStep,
  setGoalPace,
  setTargetWeight,
  setTrainingPrefs,
  getCoachingAnalysis,
  getCoachingCheckin,
  listCoachingChanges,
  revertAdjustment,
  revertCoachAction,
  removeTechniqueCue,
  type CoachingAnalysis,
  type CoachingChange,
  type CoachingChart,
  type CoachingCheckin,
  type CoachingInsight,
  type TrainingPrefs,
} from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { OnboardingScreen } from "../onboarding/OnboardingScreen";
import { CoachingProgress } from "./CoachingProgress";

// Objetivo -> rótulo + ícone (a análise gira em torno do objetivo atual).
const GOAL_META: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  emagrecimento: { label: "Emagrecimento", icon: "trending-down" },
  hipertrofia: { label: "Hipertrofia", icon: "barbell" },
  manutencao: { label: "Manutenção", icon: "remove" },
  recomposicao: { label: "Recomposição", icon: "sync" },
  performance: { label: "Performance", icon: "flash" },
};

// Rótulo curto por dimensão — pras pílulas compactas das barras "tudo certo".
const KEY_LABEL: Record<string, string> = {
  peso: "Peso",
  calorias: "Calorias",
  macros: "Macros",
  sono: "Sono",
  carga: "Carga",
  treino: "Treino",
};

// Ritmo do objetivo: rótulo + risco/benefício (o "?" de cada opção).
const PACE_META: Record<string, { label: string; info: string }> = {
  slow: {
    label: "Devagar",
    info: "Mais devagar: preserva mais músculo e é mais fácil de manter no dia a dia. O custo é levar mais tempo pra chegar no alvo.",
  },
  normal: {
    label: "Normal",
    info: "Recomendado: o equilíbrio. Resultado consistente com baixo risco de perder músculo (no corte) ou acumular gordura (no ganho).",
  },
  fast: {
    label: "Rápido",
    info: "Mais rápido: chega antes no alvo, mas sobe o risco — perder músculo no corte ou ganhar mais gordura no bulk — e é mais difícil de sustentar.",
  },
};

// "há quanto tempo no objetivo" a partir do marco (baseline). Null = sem marco.
function faseTexto(iso: string | null): string | null {
  if (!iso) return null;
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias < 7) return dias <= 0 ? "começou hoje" : `há ${dias} dia${dias === 1 ? "" : "s"}`;
  const sem = Math.round(dias / 7);
  return `há ${sem} semana${sem === 1 ? "" : "s"}`;
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
  const [changes, setChanges] = useState<CoachingChange[]>([]);
  const [checkin, setCheckin] = useState<CoachingCheckin | null>(null);
  // Gráfico aberto num modal (null = fechado). Não fica mais fixo na tela — abre
  // ao tocar o ícone de gráfico de uma barra e fecha no "x".
  const [chartOpen, setChartOpen] = useState<CoachingChart | null>(null);
  // Janela dos gráficos = a mesma da análise (o período do objetivo).
  const chartWindow = analysis?.window_days ?? 56;
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const onOpenChart = useCallback((chart: CoachingChart) => setChartOpen(chart), []);

  const load = useCallback(() => {
    if (!isPro) return Promise.resolve();
    setErro(false);
    return Promise.all([
      getCoachingAnalysis().then(setAnalysis),
      // Check-in e "o que o coach mudou" são secundários — não derrubam a tela.
      getCoachingCheckin()
        .then(setCheckin)
        .catch(() => {}),
      listCoachingChanges()
        .then(setChanges)
        .catch(() => {}),
    ])
      .catch(() => setErro(true))
      .finally(() => setLoading(false));
  }, [isPro]);

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

  // Sem onboarding de entrada: o objetivo é criado AQUI, na primeira vez que a
  // pessoa entra no Coaching. Vale pra Free e Pro (definir objetivo é básico) —
  // depois o Free vê o paywall e o Pro vê a análise. Ao concluir, recarrega.
  if (user && !user.onboarding_completed) {
    return <OnboardingScreen onDone={load} />;
  }

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
      {/* Análise do período do objetivo — o motor determinístico (sem IA) lê os
          registros. O card de objetivo + o check-in da semana vêm dentro dela,
          pra ficarem harmônicos (sem o antigo seletor de 4/8/12 semanas). */}
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
        <AnalysisView
          analysis={analysis}
          checkin={checkin}
          onApplied={onApplied}
          onOpenChart={onOpenChart}
          onOpenObjective={() => navigation.navigate("NutritionModule", { screen: "GoalSettings" })}
        />
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

      {/* O que o coach mudou — dieta + técnica + ações num painel só, enxuto:
          ativos em cima com Desfazer, o resto no histórico recolhido. */}
      {changes.length > 0 ? (
        <ChangesPanel changes={changes} onChanged={(msg) => onApplied("Pronto", msg)} />
      ) : null}

      {/* Módulos pessoais que passaram a viver dentro do Coaching. "Objetivo e
          metas" saiu daqui: agora abre tocando no card de objetivo lá em cima. */}
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
        Seus dados e análises
      </Text>

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

      {/* Gráfico em modal — abre ao tocar o ícone de gráfico de uma barra, fecha
          no "x". Não fica mais fixo ocupando a tela. */}
      <ChartModal
        chart={chartOpen}
        insights={analysis?.insights ?? []}
        periodDays={chartWindow}
        onClose={() => setChartOpen(null)}
        onDataChanged={load}
      />
    </ScrollView>
  );
}

// Modal do gráfico de uma dimensão (peso/calorias/macros/sono/carga). Reusa o
// CoachingProgress (com seu seletor interno pra trocar de gráfico) num overlay.
function ChartModal({
  chart,
  insights,
  periodDays,
  onClose,
  onDataChanged,
}: {
  chart: CoachingChart | null;
  insights: CoachingInsight[];
  periodDays: number;
  onClose: () => void;
  onDataChanged: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  // Estado local do gráfico visível — começa no que a barra pediu, e o seletor
  // interno do CoachingProgress deixa trocar sem fechar.
  const [metric, setMetric] = useState<CoachingChart>("peso");
  useEffect(() => {
    if (chart != null) setMetric(chart);
  }, [chart]);
  // O MESMO texto que aparecia na barra daquela dimensão — acompanha a troca de
  // métrica dentro do modal (carga usa a barra 'carga', não 'treino').
  const ins = insights.find((i) => i.key === metric) ?? insights.find((i) => i.chart === metric);
  const tint = ins
    ? ins.severity === "action"
      ? colors.primary
      : ins.severity === "attention"
      ? colors.warning
      : colors.success
    : colors.primary;
  return (
    <Modal visible={chart != null} transparent animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: spacing.md }}>
        <View style={{ backgroundColor: colors.surface, borderRadius: radius.card, padding: spacing.md, maxHeight: "85%" }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>Seu progresso</Text>
            <TouchableOpacity
              onPress={onClose}
              hitSlop={10}
              style={{ width: 34, height: 34, borderRadius: 17, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" }}
            >
              <Ionicons name="close" size={20} color={colors.textPrimary} />
            </TouchableOpacity>
          </View>
          {chart != null ? (
            <ScrollView keyboardShouldPersistTaps="handled">
              {/* A leitura do coach daquela dimensão (mesmo texto da barra). */}
              {ins ? (
                <View style={{ borderLeftWidth: 3, borderLeftColor: tint, paddingLeft: spacing.sm, marginBottom: spacing.md }}>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", marginBottom: 2 }]}>{ins.title}</Text>
                  <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 20 }]}>{ins.detail}</Text>
                </View>
              ) : null}
              <CoachingProgress
                periodDays={periodDays}
                metric={metric}
                onMetricChange={setMetric}
                onDataChanged={onDataChanged}
              />
            </ScrollView>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

function AnalysisView({
  analysis,
  checkin,
  onApplied,
  onOpenChart,
  onOpenObjective,
}: {
  analysis: CoachingAnalysis;
  checkin: CoachingCheckin | null;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
  onOpenObjective: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const meta = GOAL_META[analysis.goal ?? ""] ?? { label: "Seu objetivo", icon: "compass" as const };
  const fase = faseTexto(analysis.metrics.baseline_at);
  const transition = analysis.metrics.transition;

  return (
    <>
      {/* OBJETIVO & FASE — o quadro geral: o que você está buscando, há quanto
          tempo, e o balanço do período. Tocar o topo abre "Objetivo e metas". */}
      <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
        <TouchableOpacity
          onPress={onOpenObjective}
          activeOpacity={0.7}
          style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: spacing.sm }}
        >
          <View
            style={{
              width: 40, height: 40, borderRadius: 12,
              backgroundColor: colors.primary + "1F",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <Ionicons name={meta.icon} size={20} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase" }]}>
              Seu objetivo
            </Text>
            <Text style={[type.h2, { color: colors.textPrimary }]}>{meta.label}</Text>
          </View>
          {fase ? (
            <View style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 10 }}>
              <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>{fase}</Text>
            </View>
          ) : null}
          <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
        <Text style={[type.body, { color: colors.textPrimary, lineHeight: 22 }]}>{analysis.headline}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 6 }]}>
          Leitura do seu período no objetivo — confiança {analysis.confidence}.
        </Text>
        {analysis.metrics.pace && analysis.metrics.pace.options.length > 0 ? (
          <PaceSelector pace={analysis.metrics.pace} onChanged={onApplied} />
        ) : null}
        {transition?.active ? (
          <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: 10, backgroundColor: colors.surfaceAlt, borderRadius: radius.card, padding: spacing.sm }}>
            <Ionicons name="swap-vertical" size={14} color={colors.primary} style={{ marginTop: 1 }} />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 18 }]}>
              Transição de objetivo em andamento: levando sua meta de {Math.round(transition.current_kcal)} pra{" "}
              ~{Math.round(transition.target_kcal)} kcal aos poucos ({transition.remaining_kcal > 0 ? "+" : ""}
              {Math.round(transition.remaining_kcal)} restantes). Mudar devagar protege o resultado.
            </Text>
          </View>
        ) : null}
      </Card>

      {/* COMO EU MONTO SEU TREINO — ponto fraco, tempo, cardio, periodização.
          É o que o coach usa pra montar/ajustar treino e escolher técnica/deload. */}
      {analysis.metrics.training_prefs ? (
        <TrainingPrefsCard prefs={analysis.metrics.training_prefs} onChanged={onApplied} />
      ) : null}

      {/* CHECK-IN DA SEMANA — o pulso da semana atual (domingo → hoje). */}
      {checkin && checkin.has_data ? <WeeklyCheckin checkin={checkin} /> : null}

      {/* Barras em DUAS CAMADAS: em cima, em card cheio, as que pedem uma decisão
          (com ajuste primeiro); embaixo, as que estão "tudo certo" viram pílulas
          compactas — clicáveis pro gráfico, mas sem ocupar a tela. */}
      {(() => {
        const rank = (i: CoachingInsight) => (i.adjustment ? 0 : 10) + (i.severity === "action" ? 0 : 1);
        const acionaveis = analysis.insights
          .filter((i) => i.severity !== "info")
          .sort((a, b) => rank(a) - rank(b));
        const ok = analysis.insights.filter((i) => i.severity === "info");
        return (
          <>
            {acionaveis.map((ins) => (
              <InsightBar key={ins.key} ins={ins} onApplied={onApplied} onOpenChart={onOpenChart} />
            ))}
            {ok.length > 0 ? <StatusPills bars={ok} onOpenChart={onOpenChart} /> : null}
          </>
        );
      })()}

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

// Seletor de ritmo do objetivo (devagar/normal/rápido). Cada opção mostra o
// tempo estimado até o peso-alvo (ou a velocidade, sem alvo) + um "?" com o
// risco/benefício. Trocar recalcula a meta (com transição gradual se for grande).
function PaceSelector({
  pace,
  onChanged,
}: {
  pace: NonNullable<CoachingAnalysis["metrics"]["pace"]>;
  onChanged: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [saving, setSaving] = useState<string | null>(null);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);
  const [targetOpen, setTargetOpen] = useState(false);
  const [targetInput, setTargetInput] = useState(pace.target_weight_kg ? String(pace.target_weight_kg) : "");

  async function escolher(p: "slow" | "normal" | "fast") {
    if (p === pace.current || saving) return;
    setSaving(p);
    try {
      const r = await setGoalPace(p);
      onChanged("Ritmo atualizado", r.message);
    } catch {
      setSaving(null);
    }
  }

  async function salvarAlvo() {
    const kg = parseFloat(targetInput.replace(",", "."));
    setTargetOpen(false);
    try {
      const r = await setTargetWeight(Number.isFinite(kg) ? kg : null);
      onChanged("Peso-alvo", r.message);
    } catch {
      // recarrega no próximo foco
    }
  }
  async function limparAlvo() {
    setTargetOpen(false);
    setTargetInput("");
    try {
      const r = await setTargetWeight(null);
      onChanged("Peso-alvo", r.message);
    } catch {}
  }

  function tempoTexto(o: (typeof pace.options)[number]): string {
    if (o.weeks != null) {
      if (o.weeks >= 8) return `~${Math.round(o.weeks / 4)} meses`;
      return `~${o.weeks} sem`;
    }
    const r = o.rate_kg_per_week;
    return `${r > 0 ? "+" : ""}${r.toFixed(2)} kg/sem`;
  }

  return (
    <View style={{ marginTop: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.xs }]}>
        Ritmo
      </Text>
      {pace.options.map((o) => {
        const on = o.pace === pace.current;
        const m = PACE_META[o.pace];
        return (
          <View
            key={o.pace}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 10,
              borderWidth: 1,
              borderColor: on ? colors.primary : colors.border,
              backgroundColor: on ? colors.primary + "12" : "transparent",
              borderRadius: radius.card,
              paddingVertical: 9,
              paddingHorizontal: spacing.sm,
              marginBottom: spacing.xs,
            }}
          >
            <TouchableOpacity
              onPress={() => escolher(o.pace)}
              activeOpacity={0.7}
              style={{ flexDirection: "row", alignItems: "center", gap: 10, flex: 1 }}
            >
              <Ionicons
                name={on ? "radio-button-on" : "radio-button-off"}
                size={18}
                color={on ? colors.primary : colors.textSecondary}
              />
              <View style={{ flex: 1 }}>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "600" }]}>
                  {m.label}
                  {o.pace === "normal" ? "  ·  recomendado" : ""}
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                  {tempoTexto(o)} · {o.kcal} kcal
                </Text>
              </View>
              {saving === o.pace ? <ActivityIndicator size="small" color={colors.primary} /> : null}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setInfo({ title: m.label, message: m.info })} hitSlop={8}>
              <Ionicons name="help-circle-outline" size={19} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        );
      })}

      {/* Peso-alvo — a referência que dá o tempo estimado. */}
      <TouchableOpacity
        onPress={() => {
          setTargetInput(pace.target_weight_kg ? String(pace.target_weight_kg) : "");
          setTargetOpen(true);
        }}
        style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 }}
      >
        <Ionicons name="flag-outline" size={14} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "600" }]}>
          {pace.target_weight_kg ? `Peso-alvo: ${pace.target_weight_kg} kg (tocar pra mudar)` : "Definir peso-alvo pra estimar o tempo"}
        </Text>
      </TouchableOpacity>

      <InfoDialog
        visible={info != null}
        onClose={() => setInfo(null)}
        title={info?.title ?? ""}
        message={info?.message}
      />

      {/* Modal simples pra digitar o peso-alvo. */}
      <Modal visible={targetOpen} transparent animationType="fade" onRequestClose={() => setTargetOpen(false)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: spacing.lg }}>
          <View style={{ backgroundColor: colors.surface, borderRadius: radius.card, padding: spacing.lg }}>
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>Peso-alvo</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Onde você quer chegar. É a partir daqui que eu estimo o tempo de cada ritmo.
            </Text>
            <TextInput
              value={targetInput}
              onChangeText={setTargetInput}
              keyboardType="numeric"
              placeholder="ex: 75"
              placeholderTextColor={colors.textSecondary}
              style={{
                borderWidth: 1, borderColor: colors.border, borderRadius: radius.card,
                paddingVertical: 10, paddingHorizontal: spacing.md, color: colors.textPrimary,
                fontSize: 16, marginBottom: spacing.md,
              }}
            />
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Button title="Salvar" onPress={salvarAlvo} />
              </View>
              {pace.target_weight_kg ? (
                <TouchableOpacity onPress={limparAlvo} style={{ justifyContent: "center", paddingHorizontal: spacing.md }}>
                  <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Limpar</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity onPress={() => setTargetOpen(false)} style={{ justifyContent: "center", paddingHorizontal: spacing.md }}>
                  <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Cancelar</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

// "Como eu monto seu treino": ponto fraco, tempo por sessão, cardio e
// periodização. Quatro linhas simples; cada uma abre uma folha de opções com
// explicação. O coach usa tudo isto pra montar/ajustar o treino, escolher a
// técnica avançada certa e decidir quando desloadar — sem poluir a tela.
type PrefSheetField = "weak_point" | "session_length" | "cardio" | "periodization";

function TrainingPrefsCard({
  prefs,
  onChanged,
}: {
  prefs: TrainingPrefs;
  onChanged: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [sheet, setSheet] = useState<PrefSheetField | null>(null);

  async function salvar(update: Parameters<typeof setTrainingPrefs>[0], titulo: string) {
    setSheet(null);
    try {
      const r = await setTrainingPrefs(update);
      onChanged(titulo, r.message);
    } catch {
      // silencioso — recarrega no próximo foco
    }
  }

  const pontoFracoTxt = prefs.weak_point_label ?? "Nenhum";
  const tempoOpt = prefs.session_length_options.find((x) => x.value === prefs.session_length);
  const tempoTxt = tempoOpt ? `${tempoOpt.label} · ${tempoOpt.range}` : "Não definido";
  const cardioTxt = prefs.wants_cardio == null ? "Não definido" : prefs.wants_cardio ? "Com cardio" : "Sem cardio";
  const periodTxt = prefs.periodization_options.find((x) => x.value === prefs.periodization)?.label ?? "Automática";

  // Config da folha de opções aberta (título, texto e as opções + o que fazer).
  const sheetConfig =
    sheet === "weak_point"
      ? {
          title: "Ponto fraco",
          subtitle: "Um grupo pra priorizar nos acessórios. Opcional — o coach dá um empurrão extra nele quando montar o treino.",
          current: prefs.weak_point ?? "__none__",
          options: [
            { value: "__none__", label: "Nenhum" },
            ...prefs.weak_point_options.map((o) => ({ value: o.value, label: o.label })),
          ],
          pick: (v: string) => salvar({ weak_point: v === "__none__" ? null : v }, "Ponto fraco"),
        }
      : sheet === "session_length"
      ? {
          title: "Tempo por sessão",
          subtitle: "Quanto tempo você tem por treino. Define o tamanho do treino que o coach monta.",
          current: prefs.session_length ?? "",
          options: prefs.session_length_options.map((o) => ({ value: o.value, label: o.label, desc: o.range })),
          pick: (v: string) => salvar({ session_length: v as any }, "Tempo por sessão"),
        }
      : sheet === "cardio"
      ? {
          title: "Cardio",
          subtitle: "Se você quer cardio no plano. Sem cardio, o coach avisa quando o seu objetivo pedir.",
          current: prefs.wants_cardio == null ? "" : prefs.wants_cardio ? "sim" : "nao",
          options: [
            { value: "sim", label: "Com cardio", desc: "Inclui condicionamento junto da musculação." },
            { value: "nao", label: "Sem cardio", desc: "Só musculação. Bom pra quem prioriza força/massa." },
          ],
          pick: (v: string) => salvar({ wants_cardio: v === "sim" }, "Cardio"),
        }
      : sheet === "periodization"
      ? {
          title: "Periodização",
          subtitle: "Como a carga e o volume evoluem ao longo das semanas — e se tem deload.",
          current: prefs.periodization,
          options: prefs.periodization_options.map((o) => ({ value: o.value, label: o.label, desc: o.desc })),
          pick: (v: string) => salvar({ periodization: v as any }, "Periodização"),
        }
      : null;

  return (
    <Card style={{ marginBottom: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.xs }}>
        <Ionicons name="construct" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase" }]}>
          Como eu monto seu treino
        </Text>
      </View>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, lineHeight: 17 }]}>
        O coach usa isto pra montar e ajustar seu treino: priorizar um músculo, caber no seu tempo e escolher técnica e deload na hora certa.
      </Text>

      <PrefRow icon="fitness" label="Ponto fraco" value={pontoFracoTxt} onPress={() => setSheet("weak_point")} />
      <PrefRow icon="time" label="Tempo por sessão" value={tempoTxt} onPress={() => setSheet("session_length")} />
      <PrefRow icon="heart" label="Cardio" value={cardioTxt} onPress={() => setSheet("cardio")} />
      <PrefRow icon="repeat" label="Periodização" value={periodTxt} onPress={() => setSheet("periodization")} last />

      {prefs.cardio_warning ? (
        <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: spacing.sm, backgroundColor: colors.warning + "14", borderRadius: radius.card, padding: spacing.sm }}>
          <Ionicons name="alert-circle" size={15} color={colors.warning} style={{ marginTop: 1 }} />
          <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 18 }]}>{prefs.cardio_warning}</Text>
        </View>
      ) : null}

      <OptionSheet visible={sheet != null} config={sheetConfig} onClose={() => setSheet(null)} />
    </Card>
  );
}

// Uma linha da lista "Como eu monto seu treino": ícone + rótulo + valor atual.
function PrefRow({
  icon,
  label,
  value,
  onPress,
  last,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  onPress: () => void;
  last?: boolean;
}) {
  const { colors, type } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 11, borderBottomWidth: last ? 0 : 1, borderBottomColor: colors.border }}
    >
      <Ionicons name={icon} size={17} color={colors.textSecondary} />
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]}>{label}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, maxWidth: 160, textAlign: "right" }]} numberOfLines={1}>
        {value}
      </Text>
      <Ionicons name="chevron-forward" size={15} color={colors.textSecondary} />
    </TouchableOpacity>
  );
}

// Folha de opções (sobe de baixo): radio + descrição por opção. Toca e aplica.
function OptionSheet({
  visible,
  config,
  onClose,
}: {
  visible: boolean;
  config:
    | {
        title: string;
        subtitle: string;
        current: string;
        options: { value: string; label: string; desc?: string }[];
        pick: (v: string) => void;
      }
    | null;
  onClose: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" }}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}} style={{ backgroundColor: colors.surface, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: spacing.lg, paddingBottom: spacing.xl }}>
          {config ? (
            <>
              <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{config.title}</Text>
                <TouchableOpacity onPress={onClose} hitSlop={10} style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name="close" size={18} color={colors.textPrimary} />
                </TouchableOpacity>
              </View>
              <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 18 }]}>{config.subtitle}</Text>
              {config.options.map((o) => {
                const on = o.value === config.current;
                return (
                  <TouchableOpacity
                    key={o.value}
                    activeOpacity={0.7}
                    onPress={() => config.pick(o.value)}
                    style={{
                      flexDirection: "row",
                      alignItems: "flex-start",
                      gap: 10,
                      borderWidth: 1,
                      borderColor: on ? colors.primary : colors.border,
                      backgroundColor: on ? colors.primary + "12" : "transparent",
                      borderRadius: radius.card,
                      padding: spacing.sm,
                      marginBottom: spacing.xs,
                    }}
                  >
                    <Ionicons name={on ? "radio-button-on" : "radio-button-off"} size={18} color={on ? colors.primary : colors.textSecondary} style={{ marginTop: 1 }} />
                    <View style={{ flex: 1 }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "600" }]}>{o.label}</Text>
                      {o.desc ? <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>{o.desc}</Text> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </>
          ) : null}
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

// Faixa compacta das dimensões que estão "tudo certo" (info). Cada uma é uma
// pílula com bolinha verde + nome + ícone de gráfico; toca e abre o gráfico.
function StatusPills({
  bars,
  onOpenChart,
}: {
  bars: CoachingInsight[];
  onOpenChart: (chart: CoachingChart) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.xs }]}>
        Tudo certo
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
        {bars.map((b) => (
          <TouchableOpacity
            key={b.key}
            activeOpacity={0.7}
            onPress={() => b.chart && onOpenChart(b.chart)}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 6,
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.pill,
              paddingVertical: 7,
              paddingHorizontal: 11,
            }}
          >
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: colors.success }} />
            <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
              {KEY_LABEL[b.key] ?? b.title}
            </Text>
            {b.chart ? <Ionicons name="stats-chart" size={13} color={colors.textSecondary} /> : null}
          </TouchableOpacity>
        ))}
      </View>
    </View>
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

  const kind = ins.adjustment?.kind;
  const podeAplicarAcao = (kind === "progression" || kind === "deload") && !!ins.finding_key;
  const podeAplicarTransicao = kind === "transition" && !!ins.finding_key;
  const novoPeso = ins.adjustment?.new_weight;
  const rotuloAcao =
    kind === "progression"
      ? novoPeso
        ? `Mandar subir pra ${novoPeso} kg`
        : "Colocar no meu treino"
      : "Ativar semana de deload";

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

  async function aplicarAcao() {
    if (!ins.finding_key) return;
    setErro(null);
    setApplying(true);
    try {
      const r = await applyCoachAction(ins.finding_key);
      setAplicado(true);
      onApplied(r.title, r.message);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui aplicar agora."));
    } finally {
      setApplying(false);
    }
  }

  async function aplicarTransicao() {
    setErro(null);
    setApplying(true);
    try {
      const r = await applyTransitionStep();
      onApplied("Transição", r.message);
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
      ) : podeAplicarAcao ? (
        <View style={{ marginTop: spacing.sm }}>
          {aplicado ? (
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 }}>
              <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>
                Aplicado — aparece no seu treino
              </Text>
            </View>
          ) : (
            <>
              <Button
                title={applying ? "Aplicando..." : rotuloAcao}
                variant="secondary"
                compact
                loading={applying}
                onPress={aplicarAcao}
              />
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
                {kind === "deload"
                  ? "Vira um lembrete no topo dos treinos por 7 dias. Dá pra desfazer."
                  : "Vira um lembrete no exercício, no treino. Dá pra desfazer."}
              </Text>
            </>
          )}
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: 4, textAlign: "center" }]}>{erro}</Text>
          ) : null}
        </View>
      ) : podeAplicarTransicao ? (
        <View style={{ marginTop: spacing.sm }}>
          <Button
            title={applying ? "Aplicando..." : "Dar o próximo passo da transição"}
            variant="secondary"
            compact
            loading={applying}
            onPress={aplicarTransicao}
          />
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
            Ajusta a meta um degrau rumo ao alvo. Dá pra desfazer.
          </Text>
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: 4, textAlign: "center" }]}>{erro}</Text>
          ) : null}
        </View>
      ) : null}
    </Card>
  );
}

// "2026-07-21T..." -> "hoje" / "ontem" / "há N dias"
function quandoRelativo(iso: string): string {
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  return `há ${dias} dias`;
}

// Check-in semanal — o resumo proativo do coach (o que foi bem / o que precisa
// de foco), sempre da semana atual.
function WeeklyCheckin({ checkin }: { checkin: CoachingCheckin }) {
  const { colors, type, spacing } = useTheme();
  const cor = (s: string) => (s === "good" ? colors.success : s === "warn" ? colors.warning : colors.textSecondary);
  const icone = (s: string) =>
    s === "good" ? "checkmark-circle" : s === "warn" ? "alert-circle" : "ellipse-outline";
  return (
    <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Ionicons name="sparkles" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase" }]}>
          Check-in da semana
        </Text>
      </View>
      <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600", lineHeight: 22, marginBottom: spacing.sm }]}>
        {checkin.headline}
      </Text>
      {checkin.lines.map((l, i) => (
        <View key={i} style={{ flexDirection: "row", gap: 8, alignItems: "flex-start", marginTop: 6 }}>
          <Ionicons name={icone(l.status) as any} size={15} color={cor(l.status)} style={{ marginTop: 2 }} />
          <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1, lineHeight: 19 }]}>{l.text}</Text>
        </View>
      ))}
    </Card>
  );
}

// Painel unificado "O que o coach mudou": ativos em cima (com Desfazer), o
// resto no histórico recolhido. Resolve o "rest-pause não aparecia" (agora tudo
// num lugar só) e o "vai ficar comprido" (histórico não empilha).
function ChangesPanel({
  changes,
  onChanged,
}: {
  changes: CoachingChange[];
  onChanged: (message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [revertingKey, setRevertingKey] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const ativos = changes.filter((c) => c.active);
  const historico = changes.filter((c) => !c.active);

  async function desfazer(c: CoachingChange) {
    const k = `${c.source}:${c.ref_id}`;
    setRevertingKey(k);
    try {
      const r =
        c.source === "diet"
          ? await revertAdjustment(c.ref_id)
          : c.source === "technique"
          ? await removeTechniqueCue(c.ref_id)
          : await revertCoachAction(c.ref_id);
      onChanged((r as any).message ?? "Desfeito.");
    } catch {
      // silencioso — recarrega no próximo foco
    } finally {
      setRevertingKey(null);
    }
  }

  function Linha({ c, faded }: { c: CoachingChange; faded?: boolean }) {
    const k = `${c.source}:${c.ref_id}`;
    return (
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          paddingVertical: spacing.sm,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          opacity: faded ? 0.55 : 1,
        }}
      >
        <View
          style={{
            width: 30,
            height: 30,
            borderRadius: 9,
            backgroundColor: colors.surfaceAlt,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name={c.icon as any} size={16} color={faded ? colors.textSecondary : colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]} numberOfLines={1}>
            {c.title}
          </Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
            {c.subtitle} · {quandoRelativo(c.created_at)}
            {faded ? " · desfeito" : ""}
          </Text>
        </View>
        {c.active ? (
          <TouchableOpacity
            onPress={() => desfazer(c)}
            disabled={revertingKey === k}
            style={{
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.pill,
              paddingVertical: 5,
              paddingHorizontal: 12,
              opacity: revertingKey === k ? 0.5 : 1,
            }}
          >
            <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700" }]}>
              {revertingKey === k ? "..." : "Desfazer"}
            </Text>
          </TouchableOpacity>
        ) : (
          <Ionicons name="arrow-undo" size={15} color={colors.textSecondary} />
        )}
      </View>
    );
  }

  return (
    <>
      <Text
        style={[
          type.caption,
          { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm },
        ]}
      >
        O que o coach mudou
      </Text>
      <Card style={{ marginBottom: spacing.md, paddingTop: 0 }}>
        {ativos.length > 0 ? (
          ativos.map((c) => <Linha key={`${c.source}:${c.ref_id}`} c={c} />)
        ) : (
          <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
            Nenhuma mudança ativa agora.
          </Text>
        )}

        {historico.length > 0 ? (
          <>
            <TouchableOpacity
              onPress={() => setShowHistory((v) => !v)}
              style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border }}
            >
              <Ionicons name={showHistory ? "chevron-up" : "chevron-down"} size={15} color={colors.textSecondary} />
              <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "600" }]}>
                {showHistory ? "Ocultar histórico" : `Ver histórico (${historico.length})`}
              </Text>
            </TouchableOpacity>
            {showHistory ? historico.map((c) => <Linha key={`${c.source}:${c.ref_id}`} c={c} faded />) : null}
          </>
        ) : null}
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
