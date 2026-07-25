import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  applyCoachAction,
  applyDietAdjustment,
  applyTechnique,
  applyTransitionStep,
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
} from "../../api/coaching";
import { getConsistency, type ConsistencyHistory } from "../../api/evolution";
import { AtlasLogo } from "../../components/AtlasLogo";
import { Avatar } from "../../components/Avatar";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { DraggableList } from "../../components/DraggableList";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { useHomeLayout, type HomeBlockId } from "../../utils/homeLayout";
import { useProfilePhoto } from "../../utils/profilePhoto";
import { OnboardingScreen } from "../onboarding/OnboardingScreen";
import {
  ExpandToggle,
  MacroChip,
  TrainingPrefsCard,
  WorkoutCard,
} from "./coachBlocks";
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
  const insets = useSafeAreaInsets();
  const isPro = user?.plan === "pro";

  const [analysis, setAnalysis] = useState<CoachingAnalysis | null>(null);
  const [changes, setChanges] = useState<CoachingChange[]>([]);
  const [checkin, setCheckin] = useState<CoachingCheckin | null>(null);
  const [consistency, setConsistency] = useState<ConsistencyHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);
  // Trava o scroll do ScrollView externo enquanto a pessoa arrasta um bloco
  // pra reordenar a home — senão os dois gestos (scroll e arrastar) brigam.
  const [homeDragging, setHomeDragging] = useState(false);

  // Navegação do hub: null = o mapa; senão a seção aberta. O gráfico não é mais
  // um modal — vira a seção "progresso", com a métrica pré-selecionada.
  const [section, setSection] = useState<CoachingSectionId | null>(null);
  const [progressMetric, setProgressMetric] = useState<CoachingChart>("peso");

  // Ordem dos blocos da home, editável em Configurações > Layout da tela
  // inicial. Recarrega a cada foco pra pegar mudanças feitas lá.
  const homeLayout = useHomeLayout();
  useFocusEffect(
    useCallback(() => {
      homeLayout.reload();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
  );

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
    return <FreeHome navigation={navigation} user={user} />;
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.lg + insets.top, paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      scrollEnabled={!homeDragging}
    >
      {section == null ? <HomeHeader navigation={navigation} user={user} /> : null}
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
            order={homeLayout.order}
            onReorder={homeLayout.reorder}
            onDragStateChange={setHomeDragging}
            analysis={analysis}
            checkin={checkin}
            changes={changes}
            consistency={consistency}
            onApplied={onApplied}
            onOpenChart={openChart}
            onOpenSection={setSection}
            onOpenTrainingModule={() => navigation.navigate("TrainingModule")}
            onOpenDietModule={() => navigation.navigate("NutritionModule")}
            onOpenWeight={() => navigation.navigate("Weight")}
            onOpenSleep={() => navigation.navigate("Sleep")}
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

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

// Cabeçalho da home: logo + saudação + avatar (perfil) e, abaixo, as faixas
// social (Desafios / Amigos e feed). A home do app agora É o Coaching — este
// cabeçalho substitui a antiga Dashboard.
function HomeHeader({ navigation, user }: { navigation: any; user: ReturnType<typeof useAuth>["user"] }) {
  const { colors, type, spacing } = useTheme();
  const firstName = user?.display_name?.split(" ")[0] ?? "";
  const profilePhoto = useProfilePhoto();
  return (
    <View style={{ marginBottom: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
        <AtlasLogo size={22} color={colors.primary} seam={colors.bg} />
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22, flex: 1, marginLeft: spacing.sm }]} numberOfLines={1}>
          {greeting()}, {firstName}
        </Text>
        <TouchableOpacity onPress={() => navigation.navigate("Profile")}>
          <Avatar name={user?.display_name ?? "?"} handle={user?.handle ?? "?"} size={40} photoUri={profilePhoto.uri} />
        </TouchableOpacity>
      </View>
      <SocialPills navigation={navigation} />
    </View>
  );
}

// Faixa: Desafios (dispute) + Amigos e feed. Migradas da antiga Dashboard.
function SocialPills({ navigation }: { navigation: any }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: spacing.sm }}>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("Social", { screen: "Challenges" })}
        style={{ flex: 1 }}
      >
        <View
          style={{
            backgroundColor: colors.secondary,
            borderRadius: 14,
            paddingVertical: 10,
            paddingHorizontal: spacing.md,
            flexDirection: "row",
            alignItems: "center",
          }}
        >
          <Ionicons name="trophy" size={22} color="#FFFFFF" style={{ marginRight: spacing.sm }} />
          <View style={{ flex: 1 }}>
            <Text style={[type.body, { color: "#FFFFFF", fontWeight: "800" }]}>Desafios</Text>
            <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={1}>
              Dispute com seus amigos
            </Text>
          </View>
        </View>
      </TouchableOpacity>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("Social")}
        style={{
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          borderRadius: 14,
          paddingHorizontal: spacing.md,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Ionicons name="people" size={18} color={colors.moduleSocial} />
        <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700", fontSize: 10, marginTop: 2 }]}>
          Amigos e feed
        </Text>
      </TouchableOpacity>
    </View>
  );
}

// Grade de quadrados (2 por linha). Última sozinha ganha um espaçador pra não
// esticar sozinha na linha.
function TileGrid({
  tiles,
}: {
  tiles: { icon: keyof typeof Ionicons.glyphMap; title: string; subtitle: string; onPress: () => void }[];
}) {
  const { spacing } = useTheme();
  const rows: (typeof tiles)[] = [];
  for (let i = 0; i < tiles.length; i += 2) rows.push(tiles.slice(i, i + 2));
  return (
    <View style={{ gap: spacing.sm }}>
      {rows.map((row, ri) => (
        <View key={ri} style={{ flexDirection: "row", gap: spacing.sm }}>
          {row.map((t) => (
            <SectionTile key={t.title} icon={t.icon} title={t.title} subtitle={t.subtitle} onPress={t.onPress} />
          ))}
          {row.length === 1 ? <View style={{ flex: 1 }} /> : null}
        </View>
      ))}
    </View>
  );
}

/** Home do plano Free: sem coaching. Só o cabeçalho social, um convite pro Pro
 * e a grade dos módulos manuais (Treino, Dieta, Peso, Sono). Objetivo é do Pro
 * (sem IA não há o que mostrar ali). */
function FreeHome({ navigation, user }: { navigation: any; user: ReturnType<typeof useAuth>["user"] }) {
  const { colors, type, spacing, radius } = useTheme();
  const insets = useSafeAreaInsets();
  const tiles = [
    { icon: "barbell" as const, title: "Treino", subtitle: "Rotinas e métodos", onPress: () => navigation.navigate("TrainingModule") },
    { icon: "restaurant" as const, title: "Dieta", subtitle: "Refeições e água", onPress: () => navigation.navigate("NutritionModule") },
    { icon: "scale" as const, title: "Peso", subtitle: "Registrar e acompanhar", onPress: () => navigation.navigate("Weight") },
    { icon: "moon" as const, title: "Sono", subtitle: "Registrar suas noites", onPress: () => navigation.navigate("Sleep") },
  ];
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.lg + insets.top, paddingBottom: spacing.xxl }}
    >
      <HomeHeader navigation={navigation} user={user} />

      {/* Convite pro Pro — o Coaching é a diferença do plano pago. */}
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => navigation.navigate("Paywall")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: spacing.md,
          backgroundColor: colors.primary + "16",
          borderWidth: 1,
          borderColor: colors.primary + "3A",
          borderRadius: radius.card,
          padding: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: colors.primary + "26", alignItems: "center", justifyContent: "center" }}>
          <Ionicons name="compass" size={24} color={colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800" }]}>Ative seu Coaching</Text>
            <View style={{ backgroundColor: colors.primary, borderRadius: 6, paddingHorizontal: 5, paddingVertical: 1 }}>
              <Text style={{ color: colors.textOnPrimary, fontSize: 9, fontWeight: "900" }}>PRO</Text>
            </View>
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>
            Acompanhamento que ajusta treino e dieta pra você, ao longo do tempo.
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.primary} />
      </TouchableOpacity>

      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
        Seus módulos
      </Text>
      <TileGrid tiles={tiles} />
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
  order,
  onReorder,
  onDragStateChange,
  analysis,
  checkin,
  changes,
  consistency,
  onApplied,
  onOpenChart,
  onOpenSection,
  onOpenTrainingModule,
  onOpenDietModule,
  onOpenWeight,
  onOpenSleep,
  onAskCoach,
}: {
  order: HomeBlockId[];
  onReorder: (order: HomeBlockId[]) => void;
  onDragStateChange: (dragging: boolean) => void;
  analysis: CoachingAnalysis;
  checkin: CoachingCheckin | null;
  changes: CoachingChange[];
  consistency: ConsistencyHistory | null;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
  onOpenSection: (s: CoachingSectionId) => void;
  onOpenTrainingModule: () => void;
  onOpenDietModule: () => void;
  onOpenWeight: () => void;
  onOpenSleep: () => void;
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

  // Cada bloco é montado uma vez aqui; a ORDEM em que aparecem na tela vem de
  // `order` (editável em Configurações > Layout da tela inicial). Blocos
  // condicionais retornam null quando não há o que mostrar.
  const blocks: Record<HomeBlockId, React.ReactNode> = {
    hero: (
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
    ),

    missoes: (
      <View style={{ marginBottom: spacing.md }}>
        {/* MISSÕES DA SEMANA — o que fazer agora. */}
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
          {missoes.length > 0 ? `Missões da semana · ${missoes.length}` : "Missões da semana"}
        </Text>
        {missoes.length > 0 ? (
          missoes.map((ins) => <InsightBar key={ins.key} ins={ins} onApplied={onApplied} onOpenChart={onOpenChart} />)
        ) : (
          <Card accent={colors.success}>
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
      </View>
    ),

    tudo_certo: ok.length > 0 ? (
      <View style={{ marginBottom: spacing.md }}>
        <StatusPills bars={ok} onOpenChart={onOpenChart} />
      </View>
    ) : null,

    explorar: (
      <View style={{ marginBottom: spacing.md }}>
        {/* MAPA — os módulos. Objetivo abre a análise do coach aqui dentro; os
            demais abrem a tela do módulo (coach no topo + registro manual). */}
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
          Explorar
        </Text>
        <TileGrid
          tiles={[
            { icon: "flag", title: "Objetivo", subtitle: "Metas e ritmo", onPress: () => onOpenSection("objetivo") },
            {
              icon: "barbell",
              title: "Treino",
              subtitle: workout?.built ? `${workout.count} treino${workout.count === 1 ? "" : "s"}` : "Montar treino",
              onPress: onOpenTrainingModule,
            },
            {
              icon: "restaurant",
              title: "Dieta",
              subtitle: analysis.metrics.goal_kcal ? `${Math.round(analysis.metrics.goal_kcal)} kcal/dia` : "Definir meta",
              onPress: onOpenDietModule,
            },
            { icon: "scale", title: "Peso", subtitle: "Registrar e evolução", onPress: onOpenWeight },
            { icon: "moon", title: "Sono", subtitle: "Noites e recuperação", onPress: onOpenSleep },
          ]}
        />
      </View>
    ),

    pergunte_coach: (
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
          marginBottom: spacing.md,
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
    ),

    o_que_mudou: changes.length > 0 ? (
      <View style={{ marginBottom: spacing.md }}>
        <ChangesPanel changes={changes} onChanged={(msg) => onApplied("Pronto", msg)} />
      </View>
    ) : null,
  };

  // Blocos condicionais (ex: "tudo certo" sem nada ok, "o que mudou" sem
  // ajustes) ficam null — não entram na lista arrastável (não faz sentido
  // arrastar um bloco vazio), mas continuam guardando o lugar na ordem
  // salva pra reaparecerem no mesmo lugar relativo quando tiverem conteúdo.
  const visiveis = order.filter((id) => blocks[id] != null);

  function handleReorder(novaOrdemVisivel: HomeBlockId[]) {
    const escondidos = order.filter((id) => blocks[id] == null);
    const resultado = [...novaOrdemVisivel];
    escondidos.forEach((id) => {
      const idxOriginal = order.indexOf(id);
      let inserirDepoisDe: HomeBlockId | null = null;
      for (let i = idxOriginal - 1; i >= 0; i--) {
        if (resultado.includes(order[i])) {
          inserirDepoisDe = order[i];
          break;
        }
      }
      const pos = inserirDepoisDe ? resultado.indexOf(inserirDepoisDe) + 1 : 0;
      resultado.splice(pos, 0, id);
    });
    onReorder(resultado);
  }

  return (
    <DraggableList
      items={visiveis.map((id) => ({ id, node: blocks[id] }))}
      onReorder={handleReorder}
      onDragStateChange={onDragStateChange}
    />
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

// (MacroChip agora vem de ./coachBlocks — reutilizado no cabeçalho da Dieta.)

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

// (TrainingPrefsCard, WorkoutCard, ExpandToggle, PrefRow e OptionSheet foram
// movidos para ./coachBlocks e são importados no topo deste arquivo.)

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
  // Só a mudança mais recente aparece de cara; o resto (ativas e desfeitas,
  // juntas) fica atrás de UM "Ver mais" só — antes eram duas abas separadas
  // (ativos/histórico), o que espalhava a mesma informação em dois lugares.
  const [expanded, setExpanded] = useState(false);
  const visiveis = expanded ? changes : changes.slice(0, 1);
  const ocultos = changes.length - visiveis.length;

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
        {changes.length > 0 ? (
          visiveis.map((c) => <Linha key={`${c.source}:${c.ref_id}`} c={c} faded={!c.active} />)
        ) : (
          <Text style={[type.bodySmall, { color: colors.textSecondary, paddingVertical: spacing.sm }]}>
            Nenhuma mudança ativa agora.
          </Text>
        )}

        {changes.length > 1 ? (
          <TouchableOpacity
            onPress={() => setExpanded((v) => !v)}
            style={{ flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border }}
          >
            <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={15} color={colors.textSecondary} />
            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "600" }]}>
              {expanded ? "Mostrar menos" : `Ver mais (${ocultos})`}
            </Text>
          </TouchableOpacity>
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
