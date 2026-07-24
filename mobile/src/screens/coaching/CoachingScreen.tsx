import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  applyCoachAction,
  applyDietAdjustment,
  applyTechnique,
  applyTransitionStep,
  buildCoachWorkout,
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
import { getConsistency, type ConsistencyHistory } from "../../api/evolution";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { OnboardingScreen } from "../onboarding/OnboardingScreen";
import { CoachingProgress } from "./CoachingProgress";

// Seções do "mapa" do hub — cada uma abre uma tela de detalhe com o conteúdo
// denso que antes ficava tudo empilhado.
type CoachingSectionId = "objetivo" | "treino" | "dieta" | "progresso";

// Níveis de constância (gamificação). O nível vem do RECORDE de dias seguidos
// (só cresce), então "subir de nível" é permanente; o streak atual é a chama viva.
const CONSISTENCY_LEVELS = [
  { min: 0, label: "Começando" },
  { min: 3, label: "Aquecendo" },
  { min: 7, label: "Constante" },
  { min: 14, label: "Disciplinado" },
  { min: 21, label: "Focado" },
  { min: 30, label: "Imparável" },
];

function nivelConstancia(bestStreak: number): {
  level: number;
  label: string;
  floor: number;
  next: number | null;
} {
  let idx = 0;
  for (let i = 0; i < CONSISTENCY_LEVELS.length; i++) {
    if (bestStreak >= CONSISTENCY_LEVELS[i].min) idx = i;
  }
  const next = idx < CONSISTENCY_LEVELS.length - 1 ? CONSISTENCY_LEVELS[idx + 1].min : null;
  return { level: idx, label: CONSISTENCY_LEVELS[idx].label, floor: CONSISTENCY_LEVELS[idx].min, next };
}

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
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  const [analysis, setAnalysis] = useState<CoachingAnalysis | null>(null);
  const [changes, setChanges] = useState<CoachingChange[]>([]);
  const [checkin, setCheckin] = useState<CoachingCheckin | null>(null);
  const [consistency, setConsistency] = useState<ConsistencyHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);

  // Navegação do hub: null = o mapa; senão a seção aberta. O gráfico não é mais
  // um modal — vira a seção "progresso", com a métrica pré-selecionada.
  const [section, setSection] = useState<CoachingSectionId | null>(null);
  const [progressMetric, setProgressMetric] = useState<CoachingChart>("peso");

  const openChart = useCallback((chart: CoachingChart) => {
    setProgressMetric(chart);
    setSection("progresso");
  }, []);

  const load = useCallback(() => {
    if (!isPro) return Promise.resolve();
    setErro(false);
    return Promise.all([
      getCoachingAnalysis().then(setAnalysis),
      // Check-in, "o que o coach mudou" e constância são secundários — não
      // derrubam a tela se falharem.
      getCoachingCheckin()
        .then(setCheckin)
        .catch(() => {}),
      listCoachingChanges()
        .then(setChanges)
        .catch(() => {}),
      getConsistency()
        .then(setConsistency)
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
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
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
        section == null ? (
          <CoachingHub
            analysis={analysis}
            checkin={checkin}
            changes={changes}
            consistency={consistency}
            onApplied={onApplied}
            onOpenChart={openChart}
            onOpenSection={setSection}
            onAskCoach={() => navigation.navigate("CoachChat")}
          />
        ) : (
          <CoachingSectionView
            section={section}
            analysis={analysis}
            changes={changes}
            onBack={() => setSection(null)}
            onApplied={onApplied}
            progressMetric={progressMetric}
            onProgressMetric={setProgressMetric}
            onReload={load}
            onOpenObjective={() => navigation.navigate("NutritionModule", { screen: "GoalSettings" })}
            onOpenTraining={() => navigation.navigate("TrainingModule")}
            onOpenDiary={() => navigation.navigate("NutritionModule")}
            onOpenTemplates={() => navigation.navigate("NutritionModule", { screen: "DietTemplates" })}
            onOpenMeasurements={() => navigation.navigate("NutritionModule", { screen: "Measurements" })}
            onAskCoach={() => navigation.navigate("CoachChat")}
          />
        )
      ) : null}

      <InfoDialog
        visible={aviso != null}
        onClose={() => setAviso(null)}
        title={aviso?.title ?? ""}
        message={aviso?.message}
      />
    </ScrollView>
  );
}

// Semana do objetivo a partir do marco (baseline). "Semana 1", "Semana 3"...
function semanaLabel(baseline: string | null): string | null {
  if (!baseline) return null;
  const dias = Math.floor((Date.now() - new Date(baseline).getTime()) / 86400000);
  return `Semana ${dias < 7 ? 1 : Math.floor(dias / 7) + 1}`;
}

// HUB — a casa do Coaching. Um newcomer bate o olho e entende: quem é meu coach
// e em que fase estou (topo) · como estou indo, com constância gamificada
// (progresso) · o que fazer agora (missões) · pra onde ir (mapa de 4 seções).
// Tudo que é denso (prefs, gráficos, "o que mudou") mora dentro das seções.
function CoachingHub({
  analysis,
  checkin,
  changes,
  consistency,
  onApplied,
  onOpenChart,
  onOpenSection,
  onAskCoach,
}: {
  analysis: CoachingAnalysis;
  checkin: CoachingCheckin | null;
  changes: CoachingChange[];
  consistency: ConsistencyHistory | null;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
  onOpenSection: (s: CoachingSectionId) => void;
  onAskCoach: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const meta = GOAL_META[analysis.goal ?? ""] ?? { label: "Seu objetivo", icon: "compass" as const };
  const semana = semanaLabel(analysis.metrics.baseline_at);
  const leitura = checkin?.headline ?? analysis.headline;

  const rank = (i: CoachingInsight) => (i.adjustment ? 0 : 10) + (i.severity === "action" ? 0 : 1);
  const missoes = analysis.insights.filter((i) => i.severity !== "info").sort((a, b) => rank(a) - rank(b));
  const ok = analysis.insights.filter((i) => i.severity === "info");

  const streak = consistency?.current_streak ?? 0;
  const best = consistency?.best_streak ?? 0;
  const nv = nivelConstancia(best);
  const inLevel = nv.next != null ? Math.min(Math.max((best - nv.floor) / (nv.next - nv.floor), 0), 1) : 1;
  const semConstancia = streak === 0 && best === 0;

  const pace = analysis.metrics.pace;
  const alvo = pace?.target_weight_kg ?? null;
  const atual = pace?.current_weight_kg ?? analysis.metrics.weight_kg ?? null;
  const faltam = alvo != null && atual != null ? atual - alvo : null;

  const workout = analysis.metrics.workout;

  return (
    <>
      {/* HERO — coach + fase + leitura + constância gamificada. */}
      <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: spacing.sm }}>
          <View
            style={{
              width: 44, height: 44, borderRadius: 14,
              backgroundColor: colors.primary + "1F",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <Ionicons name={meta.icon} size={22} color={colors.primary} />
          </View>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase" }]}>
              Seu coaching
            </Text>
            <Text style={[type.h2, { color: colors.textPrimary }]} numberOfLines={1}>{meta.label}</Text>
          </View>
          {semana ? (
            <View style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingVertical: 5, paddingHorizontal: 11 }}>
              <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "800" }]}>{semana}</Text>
            </View>
          ) : null}
        </View>

        <Text style={[type.body, { color: colors.textPrimary, lineHeight: 22 }]}>{leitura}</Text>

        {/* Constância gamificada */}
        <View style={{ borderTopWidth: 1, borderTopColor: colors.border, marginTop: spacing.md, paddingTop: spacing.md }}>
          {semConstancia ? (
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <Ionicons name="flame-outline" size={20} color={colors.textSecondary} />
              <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1 }]}>
                Registre treino, dieta e sono no dia a dia pra construir sua constância.
              </Text>
            </View>
          ) : (
            <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.md }}>
              {/* Chama do streak */}
              <View style={{ alignItems: "center", minWidth: 66 }}>
                <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 3 }}>
                  <Ionicons name="flame" size={22} color={colors.primary} />
                  <Text style={[type.display, { color: colors.textPrimary, fontSize: 30 }]}>{streak}</Text>
                </View>
                <Text style={[type.caption, { color: colors.textSecondary }]}>dias seguidos</Text>
              </View>
              {/* Nível de constância + barra */}
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "800" }]}>
                    Nível {nv.level} · {nv.label}
                  </Text>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>recorde {best}</Text>
                </View>
                <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surfaceAlt, overflow: "hidden" }}>
                  <View style={{ width: `${inLevel * 100}%`, height: "100%", backgroundColor: colors.primary }} />
                </View>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 3 }]}>
                  {nv.next != null ? `Próximo nível ao chegar em ${nv.next} dias seguidos` : "Nível máximo — imparável!"}
                </Text>
              </View>
            </View>
          )}

          {/* Alvo de peso (quando o objetivo tem peso-alvo) */}
          {faltam != null && Math.abs(faltam) >= 0.1 ? (
            <TouchableOpacity
              onPress={() => onOpenChart("peso")}
              activeOpacity={0.7}
              style={{
                flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.md,
                backgroundColor: colors.surfaceAlt, borderRadius: radius.pill,
                paddingVertical: 7, paddingHorizontal: 12, alignSelf: "flex-start",
              }}
            >
              <Ionicons name="flag" size={13} color={colors.primary} />
              <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700" }]}>
                Alvo {alvo} kg · faltam {Math.abs(faltam).toFixed(1).replace(".", ",")} kg
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </Card>

      {/* MISSÕES DA SEMANA — o que fazer agora. */}
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
        {missoes.length > 0 ? `Missões da semana · ${missoes.length}` : "Missões da semana"}
      </Text>
      {missoes.length > 0 ? (
        missoes.map((ins) => <InsightBar key={ins.key} ins={ins} onApplied={onApplied} onOpenChart={onOpenChart} />)
      ) : (
        <Card accent={colors.success} style={{ marginBottom: spacing.sm }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <View style={{ width: 40, height: 40, borderRadius: 13, backgroundColor: colors.success + "22", alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="checkmark-done" size={22} color={colors.success} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>Tudo em dia!</Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                Sem ajustes pendentes. Siga registrando que eu aviso quando algo mudar.
              </Text>
            </View>
          </View>
        </Card>
      )}
      {ok.length > 0 ? <StatusPills bars={ok} onOpenChart={onOpenChart} /> : null}

      {/* MAPA — as 4 seções. Resolve o "caçar as coisas". */}
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginTop: spacing.sm, marginBottom: spacing.sm }]}>
        Explorar
      </Text>
      <View style={{ gap: spacing.sm }}>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <SectionTile icon="flag" title="Objetivo" subtitle="Metas e ritmo" onPress={() => onOpenSection("objetivo")} />
          <SectionTile
            icon="barbell"
            title="Treino"
            subtitle={workout?.built ? `${workout.count} treino${workout.count === 1 ? "" : "s"}` : "Montar treino"}
            onPress={() => onOpenSection("treino")}
          />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <SectionTile
            icon="restaurant"
            title="Dieta"
            subtitle={analysis.metrics.goal_kcal ? `${Math.round(analysis.metrics.goal_kcal)} kcal/dia` : "Definir meta"}
            onPress={() => onOpenSection("dieta")}
          />
          <SectionTile icon="stats-chart" title="Progresso" subtitle="Gráficos e peso" onPress={() => onOpenSection("progresso")} />
        </View>
      </View>

      {/* Pergunte ao coach */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={onAskCoach}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: spacing.md,
          backgroundColor: colors.primary + "14",
          borderWidth: 1,
          borderColor: colors.primary + "33",
          borderRadius: radius.card,
          padding: spacing.md,
          marginTop: spacing.md,
        }}
      >
        <View style={{ width: 42, height: 42, borderRadius: 14, backgroundColor: colors.primary + "22", alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="chatbubbles" size={22} color={colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>Pergunte ao coach</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
            Dúvidas sobre análise, treino, dieta e sono
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.primary} />
      </TouchableOpacity>

      {/* O que o coach mudou — histórico, discreto no fim. */}
      {changes.length > 0 ? (
        <View style={{ marginTop: spacing.lg }}>
          <ChangesPanel changes={changes} onChanged={(msg) => onApplied("Pronto", msg)} />
        </View>
      ) : null}
    </>
  );
}

// Um quadrado do mapa de seções.
function SectionTile({
  icon,
  title,
  subtitle,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  onPress: () => void;
}) {
  const { colors, type, spacing, shadow } = useTheme();
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress} style={{ flex: 1 }}>
      <View style={[{ backgroundColor: colors.surface, borderRadius: 18, padding: spacing.md, minHeight: 96 }, shadow.sm]}>
        <View style={{ width: 38, height: 38, borderRadius: 12, backgroundColor: colors.primary + "18", alignItems: "center", justifyContent: "center", marginBottom: spacing.sm }}>
          <Ionicons name={icon} size={20} color={colors.primary} />
        </View>
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800" }]}>{title}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]} numberOfLines={1}>
          {subtitle}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

// Detalhe de uma seção do mapa. Reúne o conteúdo denso (que antes ficava tudo
// empilhado) sob um cabeçalho com voltar.
function CoachingSectionView({
  section,
  analysis,
  onBack,
  onApplied,
  progressMetric,
  onProgressMetric,
  onReload,
  onOpenObjective,
  onOpenTraining,
  onOpenDiary,
  onOpenTemplates,
  onOpenMeasurements,
  onAskCoach,
}: {
  section: CoachingSectionId;
  analysis: CoachingAnalysis;
  changes: CoachingChange[];
  onBack: () => void;
  onApplied: (title: string, message: string) => void;
  progressMetric: CoachingChart;
  onProgressMetric: (m: CoachingChart) => void;
  onReload: () => void;
  onOpenObjective: () => void;
  onOpenTraining: () => void;
  onOpenDiary: () => void;
  onOpenTemplates: () => void;
  onOpenMeasurements: () => void;
  onAskCoach: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const meta = GOAL_META[analysis.goal ?? ""] ?? { label: "Seu objetivo", icon: "compass" as const };
  const fase = faseTexto(analysis.metrics.baseline_at);
  const m = analysis.metrics;
  const [expObj, setExpObj] = useState(true);

  const titulo =
    section === "objetivo"
      ? "Objetivo & metas"
      : section === "treino"
      ? "Meu treino"
      : section === "dieta"
      ? "Minha dieta"
      : "Meu progresso";

  return (
    <>
      {/* Cabeçalho da seção com voltar. */}
      <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.md }}>
        <TouchableOpacity
          onPress={onBack}
          hitSlop={8}
          style={{ width: 40, height: 40, borderRadius: 13, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" }}
        >
          <Ionicons name="arrow-back" size={20} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22 }]}>{titulo}</Text>
      </View>

      {section === "objetivo" ? (
        <ObjetivoCard
          analysis={analysis}
          meta={meta}
          fase={fase}
          transition={m.transition}
          expanded={expObj}
          onToggle={() => setExpObj((v) => !v)}
          onOpenObjective={onOpenObjective}
        />
      ) : null}

      {section === "treino" ? (
        <>
          {m.training_prefs ? <TrainingPrefsCard prefs={m.training_prefs} onChanged={onApplied} /> : null}
          <WorkoutCard workout={m.workout} onApplied={onApplied} onOpenTraining={onOpenTraining} />
        </>
      ) : null}

      {section === "dieta" ? (
        <>
          <Card style={{ marginBottom: spacing.md }}>
            <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.sm }]}>
              Sua meta atual
            </Text>
            {m.goal_kcal ? (
              <>
                <View style={{ flexDirection: "row", alignItems: "baseline", gap: 5, marginBottom: spacing.sm }}>
                  <Text style={[type.display, { color: colors.textPrimary, fontSize: 30 }]}>{Math.round(m.goal_kcal)}</Text>
                  <Text style={[type.body, { color: colors.textSecondary }]}>kcal / dia</Text>
                </View>
                <View style={{ flexDirection: "row", gap: spacing.md }}>
                  <MacroChip label="Proteína" goal={m.protein_target_g} avg={m.avg_protein_g} color={colors.moduleTraining} />
                  <MacroChip label="Carbo" goal={m.goal_carbs_g} avg={m.avg_carbs_g} color={colors.info} />
                  <MacroChip label="Gordura" goal={m.goal_fat_g} avg={m.avg_fat_g} color={colors.warning} />
                </View>
                {m.avg_kcal != null ? (
                  <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
                    Média recente: {Math.round(m.avg_kcal)} kcal/dia.
                  </Text>
                ) : null}
              </>
            ) : (
              <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                Você ainda não tem meta calórica. Defina uma pra o coach acompanhar sua dieta.
              </Text>
            )}
          </Card>

          <CoachRow icon="book" tint={colors.moduleNutrition} title="Abrir meu diário" subtitle="Registrar refeições e água de hoje" onPress={onOpenDiary} />
          <CoachRow icon="sparkles" tint={colors.primary} title="Gerar dieta com o coach" subtitle="Um cardápio na sua meta, em segundos" onPress={onAskCoach} />
          <CoachRow icon="restaurant" tint={colors.moduleTraining} title="Dietas prontas" subtitle="Cardápios prontos pra adaptar" onPress={onOpenTemplates} />
          <View style={{ marginTop: spacing.xs }}>
            <Button title="Ajustar meta calórica" variant="secondary" compact onPress={onOpenObjective} />
          </View>
        </>
      ) : null}

      {section === "progresso" ? (
        <>
          <CoachingProgress
            periodDays={analysis.window_days}
            metric={progressMetric}
            onMetricChange={onProgressMetric}
            onDataChanged={onReload}
          />
          <CoachRow
            icon="body"
            tint={colors.info}
            title="Medidas e fotos"
            subtitle="Circunferências e fotos de progresso"
            onPress={onOpenMeasurements}
          />
        </>
      ) : null}
    </>
  );
}

// Chip de macro (meta + média) na seção Dieta.
function MacroChip({ label, goal, avg, color }: { label: string; goal: number | null; avg: number | null; color: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 5, marginBottom: 2 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: color }} />
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>{label}</Text>
      </View>
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]} numberOfLines={1}>
        {goal != null ? `${Math.round(goal)}g` : "—"}
      </Text>
      {avg != null ? (
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
          méd {Math.round(avg)}g
        </Text>
      ) : null}
    </View>
  );
}

// OBJETIVO & FASE — o quadro geral: o que você está buscando, há quanto tempo,
// e o balanço do período. Tocar o topo (ou o botão) abre "Objetivo e metas".
function ObjetivoCard({
  analysis,
  meta,
  fase,
  transition,
  expanded,
  onToggle,
  onOpenObjective,
}: {
  analysis: CoachingAnalysis;
  meta: { label: string; icon: keyof typeof Ionicons.glyphMap };
  fase: string | null;
  transition: CoachingAnalysis["metrics"]["transition"];
  expanded: boolean;
  onToggle: () => void;
  onOpenObjective: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <Card accent={colors.primary}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: spacing.sm }}>
          <TouchableOpacity
            onPress={onOpenObjective}
            activeOpacity={0.7}
            style={{ flexDirection: "row", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}
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
            {/* Coluna própria pra título + selo "há N semanas" — o selo NÃO
                fica na mesma linha do título (ficava disputando largura com
                o nome do objetivo e cortava em telas estreitas de celular). */}
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase" }]}>
                Seu objetivo
              </Text>
              <Text style={[type.h2, { color: colors.textPrimary }]}>{meta.label}</Text>
              {fase ? (
                <View
                  style={{
                    alignSelf: "flex-start", marginTop: 4,
                    backgroundColor: colors.surfaceAlt, borderRadius: radius.pill,
                    paddingVertical: 4, paddingHorizontal: 10,
                  }}
                >
                  <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>{fase}</Text>
                </View>
              ) : null}
            </View>
          </TouchableOpacity>
          <ExpandToggle expanded={expanded} onPress={onToggle} />
        </View>
        <Text style={[type.body, { color: colors.textPrimary, lineHeight: 22 }]}>{analysis.headline}</Text>
        {expanded ? (
          <>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 6 }]}>
              Leitura do seu período no objetivo — confiança {analysis.confidence}.
            </Text>
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
            {/* Principais informações — o que registrar pra afinar a leitura (antes
                era um card separado; é a mesma informação do headline, detalhada). */}
            {analysis.data_gaps.length > 0 ? (
              <View style={{ marginTop: spacing.sm }}>
                <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700", marginBottom: 2 }]}>
                  {analysis.has_enough_data ? "Pra afinar a leitura" : "Me dê um pouco mais pra trabalhar"}
                </Text>
                {analysis.data_gaps.map((g, i) => (
                  <View key={i} style={{ flexDirection: "row", gap: 8, marginTop: 6 }}>
                    <Ionicons name="ellipse" size={7} color={colors.primary} style={{ marginTop: 7 }} />
                    <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1, lineHeight: 19 }]}>{g}</Text>
                  </View>
                ))}
              </View>
            ) : null}
            {/* Alterar objetivo — abre a tela de objetivo (o ritmo mora lá agora). */}
            <View style={{ marginTop: spacing.md }}>
              <Button title="Alterar objetivo e ritmo" variant="secondary" compact onPress={onOpenObjective} />
            </View>
          </>
        ) : null}
    </Card>
  );
}

// "Como eu monto seu treino": ponto fraco, tempo por sessão, cardio e
// periodização. Quatro linhas simples; cada uma abre uma folha de opções com
// explicação. O coach usa tudo isto pra montar/ajustar o treino, escolher a
// técnica avançada certa e decidir quando desloadar — sem poluir a tela.
type PrefSheetField = "weak_point" | "session_length" | "training_days" | "cardio" | "periodization";

function TrainingPrefsCard({
  prefs,
  onChanged,
}: {
  prefs: TrainingPrefs;
  onChanged: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [sheet, setSheet] = useState<PrefSheetField | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function salvar(update: Parameters<typeof setTrainingPrefs>[0], titulo: string) {
    setSheet(null);
    try {
      const r = await setTrainingPrefs(update);
      onChanged(titulo, r.message);
    } catch {
      // silencioso — recarrega no próximo foco
    }
  }

  const pontoFracoTxt = prefs.weak_points_labels.length ? prefs.weak_points_labels.join(" + ") : "Nenhum";
  const tempoOpt = prefs.session_length_options.find((x) => x.value === prefs.session_length);
  const tempoTxt = tempoOpt ? `${tempoOpt.label} · ${tempoOpt.range}` : "Não definido";
  const diasTxt = prefs.training_days_per_week ? `${prefs.training_days_per_week}× por semana` : "Automático";
  const cardioTxt = prefs.wants_cardio == null ? "Não definido" : prefs.wants_cardio ? "Com cardio" : "Sem cardio";
  const periodTxt = prefs.periodization_options.find((x) => x.value === prefs.periodization)?.label ?? "Automática";

  // Config da folha de opções aberta (título, texto e as opções + o que fazer).
  const sheetConfig =
    sheet === "weak_point"
      ? {
          title: "Ponto fraco",
          subtitle: `Grupos pra priorizar nos acessórios — pode escolher até ${prefs.weak_points_max}. Opcional: o coach dá um empurrão extra neles ao montar o treino.`,
          multi: true,
          maxSelected: prefs.weak_points_max,
          selected: prefs.weak_points,
          options: prefs.weak_point_options.map((o) => ({ value: o.value, label: o.label })),
          onSaveMulti: (values: string[]) => salvar({ weak_points: values }, "Ponto fraco"),
        }
      : sheet === "session_length"
      ? {
          title: "Tempo por sessão",
          subtitle: "Quanto tempo você tem por treino. Define o tamanho do treino que o coach monta.",
          current: prefs.session_length ?? "",
          options: prefs.session_length_options.map((o) => ({ value: o.value, label: o.label, desc: o.range })),
          pick: (v: string) => salvar({ session_length: v as any }, "Tempo por sessão"),
        }
      : sheet === "training_days"
      ? {
          title: "Dias por semana",
          subtitle: "Quantos dias você pode treinar. É por aqui que o coach decide quantos treinos montar (2 a 7). No automático, ele infere pelos dias do seu perfil.",
          current: prefs.training_days_per_week ? String(prefs.training_days_per_week) : "__auto__",
          options: [
            { value: "__auto__", label: "Automático", desc: "O coach usa os dias que você marcou no perfil." },
            ...prefs.training_days_options.map((n) => ({
              value: String(n),
              label: `${n} dias`,
              desc:
                n <= 2
                  ? "Full body — cada grupo ~2× na semana."
                  : n <= 4
                  ? "Superior/inferior — 2× por grupo, bem equilibrado."
                  : "Push/pull/pernas repetido — volume alto, 2×+ por grupo.",
            })),
          ],
          pick: (v: string) =>
            salvar({ training_days_per_week: v === "__auto__" ? null : parseInt(v, 10) }, "Dias por semana"),
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

  // Resumo curto pro estado recolhido: os valores atuais numa linha só.
  const resumo = `${diasTxt} · ${pontoFracoTxt === "Nenhum" ? "sem ponto fraco" : pontoFracoTxt}`;

  return (
    <Card style={{ marginBottom: spacing.md }}>
      <TouchableOpacity
        onPress={() => setExpanded((v) => !v)}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
      >
        <Ionicons name="construct" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", flex: 1 }]}>
          Como eu monto seu treino
        </Text>
        <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]}>
        {expanded
          ? "O coach usa isto pra montar e ajustar seu treino: priorizar um músculo, caber nos seus dias e no seu tempo, e escolher técnica e deload na hora certa."
          : resumo}
      </Text>

      {expanded ? (
        <View style={{ marginTop: spacing.xs }}>
          <PrefRow icon="fitness" label="Ponto fraco" value={pontoFracoTxt} onPress={() => setSheet("weak_point")} />
          <PrefRow icon="calendar" label="Dias por semana" value={diasTxt} onPress={() => setSheet("training_days")} />
          <PrefRow icon="time" label="Tempo por sessão" value={tempoTxt} onPress={() => setSheet("session_length")} />
          <PrefRow icon="heart" label="Cardio" value={cardioTxt} onPress={() => setSheet("cardio")} />
          <PrefRow icon="repeat" label="Periodização" value={periodTxt} onPress={() => setSheet("periodization")} last />

          {prefs.cardio_warning ? (
            <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: spacing.sm, backgroundColor: colors.warning + "14", borderRadius: radius.card, padding: spacing.sm }}>
              <Ionicons name="alert-circle" size={15} color={colors.warning} style={{ marginTop: 1 }} />
              <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 18 }]}>{prefs.cardio_warning}</Text>
            </View>
          ) : null}
        </View>
      ) : null}

      <OptionSheet visible={sheet != null} config={sheetConfig} onClose={() => setSheet(null)} />
    </Card>
  );
}

// "Seu treino": o treino completo que o coach monta a partir das preferências.
// Sem treino → botão pra montar; com treino → mostra as rotinas (o que já foi
// aplicado) + refazer. Trocar UM exercício específico é nas barras de aviso.
function WorkoutCard({
  workout,
  onApplied,
  onOpenTraining,
}: {
  workout: CoachingAnalysis["metrics"]["workout"];
  onApplied: (title: string, message: string) => void;
  onOpenTraining: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [building, setBuilding] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const built = !!workout?.built;

  async function montar() {
    setErro(null);
    setBuilding(true);
    try {
      const r = await buildCoachWorkout();
      const extra = r.cardio_note ? `\n\n${r.cardio_note}` : "";
      const tecnica = r.technique_note ? `\n\n${r.technique_note}` : "";
      const foco = r.weak_point_label ? ` Priorizei ${r.weak_point_label}.` : "";
      onApplied("Treino montado", `${r.message}${foco}${extra}${tecnica}`);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui montar agora."));
    } finally {
      setBuilding(false);
    }
  }

  const resumo =
    built && workout
      ? `${workout.count} treino${workout.count === 1 ? "" : "s"} · ${workout.total_exercises} exercícios no total.`
      : "Ainda não montei seu treino — abra pra montar com suas preferências.";

  return (
    <Card style={{ marginBottom: spacing.md }}>
      <TouchableOpacity
        onPress={() => setExpanded((v) => !v)}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
      >
        <Ionicons name="barbell" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", flex: 1 }]}>
          Seu treino
        </Text>
        {built ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <Ionicons name="checkmark-circle" size={14} color={colors.success} />
            <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>Aplicado</Text>
          </View>
        ) : null}
        <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]}>{resumo}</Text>

      {expanded ? (
        built && workout ? (
          <View style={{ marginTop: spacing.xs }}>
            {workout.routines.map((r) => (
              <TouchableOpacity
                key={r.id}
                onPress={onOpenTraining}
                activeOpacity={0.7}
                style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 9, borderTopWidth: 1, borderTopColor: colors.border }}
              >
                <View style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name="fitness" size={14} color={colors.primary} />
                </View>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]} numberOfLines={1}>
                  {r.name}
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>{r.exercises} ex.</Text>
                <Ionicons name="chevron-forward" size={15} color={colors.textSecondary} />
              </TouchableOpacity>
            ))}
            <View style={{ marginTop: spacing.md }}>
              <Button
                title={building ? "Montando..." : "Refazer com base nas minhas preferências"}
                variant="secondary"
                compact
                loading={building}
                onPress={montar}
              />
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
                Arquiva o treino atual e monta um novo. Seu histórico continua intacto.
              </Text>
            </View>
          </View>
        ) : (
          <View style={{ marginTop: spacing.sm }}>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 17 }]}>
              Deixa que eu monto seu treino completo com base no que você definiu acima — dias por semana, ponto fraco,
              tempo por sessão e periodização. Fica salvo nas suas rotinas, pronto pra treinar.
            </Text>
            <Button title={building ? "Montando..." : "Montar meu treino"} loading={building} onPress={montar} />
          </View>
        )
      ) : null}
      {erro ? (
        <Text style={[type.caption, { color: colors.warning, marginTop: 6, textAlign: "center" }]}>{erro}</Text>
      ) : null}
    </Card>
  );
}

// Setinha de expandir/recolher (a "aba horizontal" abre e fecha). Botão próprio,
// pra usar ao lado de um título que já tem outra ação (ex.: o card de objetivo,
// cujo título navega).
function ExpandToggle({ expanded, onPress }: { expanded: boolean; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
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
      <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={16} color={colors.textSecondary} />
    </TouchableOpacity>
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
// `multi`: vira multi-seleção (checkbox) com teto `maxSelected` e botão Salvar —
// usado no ponto fraco (até 2). Sem `multi`, é seleção única (toca e aplica).
type SheetConfig = {
  title: string;
  subtitle: string;
  options: { value: string; label: string; desc?: string }[];
  // seleção única
  current?: string;
  pick?: (v: string) => void;
  // multi-seleção
  multi?: boolean;
  maxSelected?: number;
  selected?: string[];
  onSaveMulti?: (values: string[]) => void;
};

function OptionSheet({
  visible,
  config,
  onClose,
}: {
  visible: boolean;
  config: SheetConfig | null;
  onClose: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [sel, setSel] = useState<string[]>([]);
  const maxSel = config?.maxSelected ?? 2;
  // Ao abrir uma folha multi, começa da seleção atual salva.
  useEffect(() => {
    if (visible && config?.multi) setSel(config.selected ?? []);
  }, [visible, config?.multi, config?.selected]);

  function toggle(v: string) {
    setSel((cur) => {
      if (cur.includes(v)) return cur.filter((x) => x !== v);
      if (cur.length >= maxSel) return cur; // trava no teto
      return [...cur, v];
    });
  }

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
                const on = config.multi ? sel.includes(o.value) : o.value === config.current;
                const atCap = !!config.multi && !on && sel.length >= maxSel;
                return (
                  <TouchableOpacity
                    key={o.value}
                    activeOpacity={0.7}
                    disabled={atCap}
                    onPress={() => (config.multi ? toggle(o.value) : config.pick?.(o.value))}
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
                      opacity: atCap ? 0.45 : 1,
                    }}
                  >
                    <Ionicons
                      name={
                        config.multi
                          ? on
                            ? "checkbox"
                            : "square-outline"
                          : on
                          ? "radio-button-on"
                          : "radio-button-off"
                      }
                      size={18}
                      color={on ? colors.primary : colors.textSecondary}
                      style={{ marginTop: 1 }}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "600" }]}>{o.label}</Text>
                      {o.desc ? <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>{o.desc}</Text> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
              {config.multi ? (
                <View style={{ marginTop: spacing.sm }}>
                  <Button
                    title={sel.length ? `Salvar (${sel.length} de ${maxSel})` : "Salvar — nenhum"}
                    onPress={() => config.onSaveMulti?.(sel)}
                  />
                </View>
              ) : null}
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
  const [showAllActive, setShowAllActive] = useState(false);

  const ativos = changes.filter((c) => c.active);
  const historico = changes.filter((c) => !c.active);
  // Teto nos ATIVOS também — quando o coach mexe em vários exercícios a lista
  // enchia a tela. Mostra os 3 mais recentes; o resto colapsa atrás de "ver mais".
  const ACTIVE_CAP = 3;
  const ativosVisiveis = showAllActive ? ativos : ativos.slice(0, ACTIVE_CAP);
  const ativosOcultos = ativos.length - ativosVisiveis.length;

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
          ativosVisiveis.map((c) => <Linha key={`${c.source}:${c.ref_id}`} c={c} />)
        ) : (
          <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
            Nenhuma mudança ativa agora.
          </Text>
        )}

        {ativosOcultos > 0 || (showAllActive && ativos.length > ACTIVE_CAP) ? (
          <TouchableOpacity
            onPress={() => setShowAllActive((v) => !v)}
            style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border }}
          >
            <Ionicons name={showAllActive ? "chevron-up" : "chevron-down"} size={15} color={colors.textSecondary} />
            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "600" }]}>
              {showAllActive ? "Mostrar menos" : `Ver mais (${ativosOcultos})`}
            </Text>
          </TouchableOpacity>
        ) : null}

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
        No plano Free você continua registrando calorias e água, usando as dietas prontas, montando suas rotinas
        e os 10 métodos de treino.
      </Text>
    </ScrollView>
  );
}
