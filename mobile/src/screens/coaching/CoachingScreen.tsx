import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation, useRoute } from "@react-navigation/native";
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
  type LearnedModel,
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
import { ObjectiveScreen } from "../objective/ObjectiveScreen";
import { OnboardingScreen } from "../onboarding/OnboardingScreen";
import { WorkoutCard } from "./coachBlocks";
import { CoachingProgress } from "./CoachingProgress";

// Seções do "mapa" do hub — cada uma abre uma tela de detalhe com o conteúdo
// denso que antes ficava tudo empilhado.
type CoachingSectionId = "objetivo" | "treino" | "dieta" | "progresso";

// O NÍVEL de constância ("Nível 0 · Começando", com barra de progresso até o
// próximo) saiu do card de abertura junto com o redesenho: quem instalou o app
// pra emagrecer abria e via, em primeiro lugar, o próprio nível NO APP em vez do
// próprio peso. O que sobreviveu do conceito são os dois números que significam
// algo fora daqui — o streak atual e o recorde — nas pílulas do HeroCoaching.

/** O card que ABRE o app: onde você está e quanto falta.
 *
 * A versão anterior abria com "Nível 0 · Começando" e uma barra de nível de
 * constância. Era gamificação sobre gamificação: quem instalou pra emagrecer
 * abria o app e a primeira informação era o próprio nível no app, não o próprio
 * peso. Aqui o número grande é o que a pessoa veio ver — quanto falta pra meta —
 * e a constância volta ao tamanho que ela tem: duas pílulas de apoio.
 *
 * Sem peso-alvo (manutenção, performance) a manchete vira a constância, que aí
 * passa a ser o dado principal de verdade em vez de enfeite.
 */
function HeroCoaching({
  meta,
  semana,
  alvo,
  atual,
  inicial,
  faltam,
  streak,
  best,
  semConstancia,
  onOpenChart,
}: {
  meta: { label: string; icon: keyof typeof Ionicons.glyphMap };
  semana: string | null;
  alvo: number | null;
  atual: number | null;
  inicial: number | null;
  faltam: number | null;
  streak: number;
  best: number;
  semConstancia: boolean;
  onOpenChart: (chart: CoachingChart) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const temMeta = faltam != null && alvo != null && atual != null && Math.abs(faltam) >= 0.1;

  // Quanto do caminho já foi andado — do peso de PARTIDA até o alvo.
  //
  // A régua tem que vir de fora: "o que falta" É, por definição, a distância
  // entre o peso de hoje e o alvo, então qualquer conta feita só com esses dois
  // números dá sempre o mesmo resultado (a primeira versão desta barra ficava
  // permanentemente vazia por isso). Sem peso inicial registrado — pessoa que
  // acabou de definir a meta — a barra não aparece, em vez de mostrar um
  // progresso inventado.
  const percurso = temMeta && inicial != null ? Math.abs(inicial - alvo!) : 0;
  const progresso = percurso >= 0.1 ? Math.min(Math.max(1 - Math.abs(faltam!) / percurso, 0), 1) : null;

  const fmt = (n: number) => n.toFixed(1).replace(".", ",");

  return (
    <Card style={{ marginBottom: spacing.md }}>
      {/* Cabeçalho: quem está falando, sobre o quê, e há quanto tempo */}
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <View
          style={{
            width: 44, height: 44, borderRadius: radius.chip + 2,
            backgroundColor: colors.primary + "1F",
            alignItems: "center", justifyContent: "center",
          }}
        >
          <Ionicons name={meta.icon} size={22} color={colors.primary} />
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.8, textTransform: "uppercase", fontWeight: "700" }]}>
            Seu coaching
          </Text>
          <Text style={[type.h2, { color: colors.textPrimary }]} numberOfLines={1}>{meta.label}</Text>
          <Text style={[type.caption, { color: colors.textSecondary }]}>Seu plano atual</Text>
        </View>
        {semana ? (
          <View
            style={{
              borderWidth: 1, borderColor: colors.primary,
              borderRadius: radius.pill, paddingVertical: 5, paddingHorizontal: 11,
            }}
          >
            <Text style={[type.caption, { color: colors.primary, fontWeight: "800" }]}>{semana}</Text>
          </View>
        ) : null}
      </View>

      <View style={{ height: 1, backgroundColor: colors.border, marginVertical: spacing.md }} />

      {/* A MANCHETE. O número em destaque é o que a pessoa veio ver. */}
      {temMeta ? (
        <TouchableOpacity activeOpacity={0.7} onPress={() => onOpenChart("peso")}>
          <Text style={[type.h1, { color: colors.textPrimary, textAlign: "center" }]}>
            Faltam{" "}
            <Text style={{ color: colors.primary }}>{fmt(Math.abs(faltam!))} kg</Text>
            {" "}para sua meta
          </Text>
          <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: spacing.md }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{fmt(atual!)} kg</Text>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{fmt(alvo!)} kg</Text>
          </View>
          <View
            style={{
              height: 10, borderRadius: radius.pill, backgroundColor: colors.surfaceAlt,
              overflow: "hidden", marginTop: 6,
            }}
          >
            {progresso != null ? (
              <View style={{ width: `${progresso * 100}%`, height: "100%", backgroundColor: colors.primary, borderRadius: radius.pill }} />
            ) : null}
          </View>
        </TouchableOpacity>
      ) : (
        <View style={{ alignItems: "center" }}>
          <Text style={[type.h1, { color: colors.textPrimary, textAlign: "center" }]}>
            {semConstancia ? (
              "Comece registrando seu dia"
            ) : (
              <>
                <Text style={{ color: colors.primary }}>{streak}</Text>
                {streak === 1 ? " dia seguido" : " dias seguidos"}
              </>
            )}
          </Text>
          <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: 4 }]}>
            {semConstancia
              ? "Treino, dieta e sono no dia a dia — é o que constrói sua constância."
              : "Constância é o que faz o plano funcionar."}
          </Text>
        </View>
      )}

      {/* Constância, no tamanho dela: apoio, não manchete. */}
      <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
        <PilulaHero icone="flame" texto={`${streak} ${streak === 1 ? "dia seguido" : "dias seguidos"}`} />
        <PilulaHero icone="trophy" texto={`Recorde: ${best} ${best === 1 ? "dia" : "dias"}`} />
      </View>
    </Card>
  );
}

/** Pílula de apoio do card-herói — as duas dividem a largura em partes iguais
 * pra o card ter uma base simétrica, como na referência. */
function PilulaHero({ icone, texto }: { icone: keyof typeof Ionicons.glyphMap; texto: string }) {
  const { colors, type, radius, spacing } = useTheme();
  return (
    <View
      style={{
        flex: 1,
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        backgroundColor: colors.surfaceAlt,
        borderRadius: radius.pill,
        paddingVertical: spacing.sm,
        paddingHorizontal: spacing.sm,
      }}
    >
      <Ionicons name={icone} size={14} color={colors.primary} />
      <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700" }]} numberOfLines={1}>
        {texto}
      </Text>
    </View>
  );
}

// Objetivo -> rótulo + ícone (a análise gira em torno do objetivo atual).
const GOAL_META: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  emagrecimento: { label: "Emagrecimento", icon: "trending-down" },
  hipertrofia: { label: "Hipertrofia", icon: "barbell-outline" },
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
  const route = useRoute<any>();
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
  // As alcinhas de arrastar só aparecem depois que a pessoa toca em
  // "Reordenar" — do contrário elas ficam poluindo a Home o tempo todo.
  const [modoReordenar, setModoReordenar] = useState(false);

  // Navegação do hub: null = o mapa; senão a seção aberta. O gráfico não é mais
  // um modal — vira a seção "progresso", com a métrica pré-selecionada.
  const [section, setSection] = useState<CoachingSectionId | null>(route.params?.section ?? null);
  // Outras telas mandam direto pra uma seção (ex.: "Isso agora fica na aba
  // Objetivo" de GoalSettingsScreen) via navigate("Home", { section: "..." }).
  useFocusEffect(
    useCallback(() => {
      if (route.params?.section) setSection(route.params.section);
    }, [route.params?.section])
  );
  const [progressMetric, setProgressMetric] = useState<CoachingChart>("peso");
  // Quem rola esta tela é este ScrollView. A aba Objetivo vive dentro dele
  // (dois ScrollViews aninhados brigariam pelo gesto), então ela pede a
  // rolagem pro topo por aqui ao trocar de etapa do questionário.
  const scrollRef = React.useRef<ScrollView>(null);
  const scrollTop = useCallback(() => scrollRef.current?.scrollTo({ y: 0, animated: true }), []);

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

  // QUEM É FREE NUNCA RESPONDE QUESTIONÁRIO. Criar conta dá acesso imediato ao
  // app manual (dieta, treino, peso, sono) — nada de formulário antes de
  // conhecer o produto. O questionário é o cadastro do PRO: é ele que alimenta
  // o coach, e só faz sentido pra quem tem coach.
  //
  // A ordem destes dois blocos É a regra: antes, o `!onboarding_completed`
  // vinha primeiro e pegava todo mundo, então quem criava conta levava um
  // formulário de 9 etapas na cara antes de ver qualquer tela do app.
  if (!isPro) {
    return <FreeHome navigation={navigation} user={user} />;
  }

  // Pro sem questionário respondido: aqui ele é o cadastro do Coaching.
  if (user && !user.onboarding_completed) {
    return <OnboardingScreen onDone={load} />;
  }

  return (
    <ScrollView
      ref={scrollRef}
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
          <>
            <View style={{ flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.sm }}>
              <TouchableOpacity
                onPress={() => setModoReordenar((v) => !v)}
                activeOpacity={0.8}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 5,
                  backgroundColor: modoReordenar ? colors.primary : colors.surfaceAlt,
                  borderRadius: 999,
                  paddingVertical: 6,
                  paddingHorizontal: 12,
                }}
              >
                <Ionicons
                  name={modoReordenar ? "checkmark" : "reorder-three"}
                  size={14}
                  color={modoReordenar ? colors.textOnPrimary : colors.textSecondary}
                />
                <Text
                  style={[
                    type.caption,
                    { color: modoReordenar ? colors.textOnPrimary : colors.textSecondary, fontWeight: "700" },
                  ]}
                >
                  {modoReordenar ? "Pronto" : "Reordenar"}
                </Text>
              </TouchableOpacity>
            </View>
            <CoachingHub
              order={homeLayout.order}
              onReorder={homeLayout.reorder}
              onDragStateChange={setHomeDragging}
              editMode={modoReordenar}
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
          </>
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
            onOpenTraining={() => navigation.navigate("TrainingModule")}
            onOpenDiary={() => navigation.navigate("NutritionModule")}
            onOpenTemplates={() => navigation.navigate("NutritionModule", { screen: "DietTemplates" })}
            onOpenMeasurements={() => navigation.navigate("NutritionModule", { screen: "Measurements" })}
            onAskCoach={() => navigation.navigate("CoachChat")}
            onScrollTop={scrollTop}
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
          <Ionicons name="trophy" size={22} color={colors.textOnPrimary} style={{ marginRight: spacing.sm }} />
          <View style={{ flex: 1 }}>
            <Text style={[type.body, { color: colors.textOnPrimary, fontWeight: "800" }]}>Desafios</Text>
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
        <Ionicons name="people-outline" size={18} color={colors.moduleSocial} />
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
    { icon: "barbell-outline" as const, title: "Treino", subtitle: "Rotinas e métodos", onPress: () => navigation.navigate("TrainingModule") },
    { icon: "restaurant-outline" as const, title: "Dieta", subtitle: "Refeições e água", onPress: () => navigation.navigate("NutritionModule") },
    { icon: "scale-outline" as const, title: "Peso", subtitle: "Registrar e acompanhar", onPress: () => navigation.navigate("Weight") },
    { icon: "moon-outline" as const, title: "Sono", subtitle: "Registrar suas noites", onPress: () => navigation.navigate("Sleep") },
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
          <Ionicons name="compass-outline" size={24} color={colors.primary} />
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
/** "O QUE EU APRENDI COM VOCÊ" — os parâmetros que o coach MEDIU nesta pessoa
 * e já usa nas contas do plano dela (gasto energético real, quanto volume ela
 * aguenta, o ritmo dela por série).
 *
 * Por que isto existe como tela e não só como número escondido: o motor mudar
 * sozinho, em silêncio, é indistinguível de um motor com bug — a pessoa vê a
 * meta de caloria mudar, não entende por quê, e conclui que o app é aleatório.
 * Cada linha aqui vem com a evidência que a justifica.
 *
 * Enquanto ele ainda não sabe nada, o bloco diz isso com honestidade em vez de
 * sumir: saber que o coach está aprendendo é parte do valor. */
function AprendizadoBlock({ learned }: { learned: LearnedModel | null }) {
  const { colors, type, spacing, radius } = useTheme();
  const [verTudo, setVerTudo] = React.useState(false);
  const descobertas = learned?.descobertas ?? [];
  if (!learned) return null;

  const ordem: (keyof Pick<LearnedModel, "energia" | "tolerancia_volume" | "ritmo_sessao">)[] = [
    "energia",
    "tolerancia_volume",
    "ritmo_sessao",
  ];
  const params = ordem.map((k) => learned[k]).filter(Boolean);
  const sabidos = params.filter((p) => p.confianca !== "nenhuma");

  // O selo responde UMA pergunta: o quanto dá pra confiar neste número. Os
  // rótulos anteriores ("primeiros sinais", "já dá pra confiar", "bem medido")
  // eram frases soltas — a pessoa não sabia se aquilo era elogio, aviso ou
  // status. "Confiança baixa/média/alta" é escala, e escala se entende sem
  // legenda.
  const FORCA: Record<string, { rotulo: string; cor: string }> = {
    baixa: { rotulo: "confiança baixa", cor: colors.textSecondary },
    media: { rotulo: "confiança média", cor: colors.primary },
    alta: { rotulo: "confiança alta", cor: colors.success },
  };

  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text
        style={[
          type.caption,
          { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm },
        ]}
      >
        O que eu aprendi com você
      </Text>

      {sabidos.length === 0 ? (
        <Card>
          <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 10 }}>
            <View
              style={{
                width: 38,
                height: 38,
                borderRadius: 13,
                backgroundColor: colors.primary + "22",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Ionicons name="school-outline" size={20} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
                Ainda estou te conhecendo
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>
                Por enquanto seu plano usa as fórmulas padrão. Conforme você registra comida, peso e
                treinos, eu meço como o SEU corpo responde e troco a fórmula pelos seus números.
              </Text>
            </View>
          </View>
        </Card>
      ) : (
        <Card padded={false}>
          {sabidos.map((p, i) => {
            const forca = FORCA[p.confianca] ?? FORCA.baixa;
            return (
              <View
                key={p.chave}
                style={{
                  padding: spacing.md,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 3 }}>
                  <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>
                    {learned.rotulos?.[p.chave] ?? p.chave}
                  </Text>
                  <View
                    style={{
                      backgroundColor: forca.cor + "22",
                      borderRadius: radius.pill,
                      paddingVertical: 2,
                      paddingHorizontal: 8,
                      // Sem isto o badge era ESPREMIDO pelo título (que tem
                      // flex:1): num título de duas linhas o selo perdia
                      // largura e "já dá pra confiar" aparecia cortado como
                      // "já dá pra". O selo tem tamanho próprio; quem cede
                      // espaço é o título.
                      flexShrink: 0,
                    }}
                  >
                    <Text
                      numberOfLines={1}
                      style={[type.caption, { color: forca.cor, fontWeight: "700", fontSize: 10 }]}
                    >
                      {forca.rotulo}
                    </Text>
                  </View>
                </View>
                <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 17 }]}>
                  {p.evidencia}
                </Text>
              </View>
            );
          })}
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 6,
              paddingHorizontal: spacing.md,
              paddingBottom: spacing.md,
            }}
          >
            <Ionicons name="checkmark-circle" size={13} color={colors.success} />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>
              Esses números já são usados pra montar seu treino e sua dieta.
            </Text>
          </View>
        </Card>
      )}

      {/* AS DESCOBERTAS — o outro tipo de aprendizado. Acima estão parâmetros
          DELA que entram nas contas; aqui, padrões que só aparecem cruzando
          módulos diferentes (sono × treino, água × rendimento, comida × carga
          do dia seguinte). A lista CRESCE conforme ela registra: no começo não
          aparece nada, e é assim mesmo — inventar padrão com 3 dias de dado
          seria o oposto de aprender. */}
      {descobertas.length > 0 ? (
        <View style={{ marginTop: spacing.md }}>
          <Text
            style={[
              type.caption,
              { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm },
            ]}
          >
            O que eu cruzei dos seus dados
          </Text>
          <Card padded={false}>
            {(verTudo ? descobertas : descobertas.slice(0, 3)).map((d, i) => {
              const forca = FORCA[d.confianca] ?? FORCA.baixa;
              return (
                <View
                  key={d.chave}
                  style={{ padding: spacing.md, borderTopWidth: i === 0 ? 0 : 1, borderTopColor: colors.border }}
                >
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 3 }}>
                    <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>
                      {d.titulo}
                    </Text>
                    <View
                      style={{
                        backgroundColor: forca.cor + "22",
                        borderRadius: radius.pill,
                        paddingVertical: 2,
                        paddingHorizontal: 8,
                        flexShrink: 0,
                      }}
                    >
                      <Text numberOfLines={1} style={[type.caption, { color: forca.cor, fontWeight: "700", fontSize: 10 }]}>
                        {forca.rotulo}
                      </Text>
                    </View>
                  </View>
                  <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 17 }]}>{d.frase}</Text>
                </View>
              );
            })}
            {descobertas.length > 3 ? (
              <TouchableOpacity
                onPress={() => setVerTudo((v) => !v)}
                style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, padding: spacing.md, borderTopWidth: 1, borderTopColor: colors.border }}
              >
                <Ionicons name={verTudo ? "chevron-up" : "chevron-down"} size={14} color={colors.primary} />
                <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>
                  {verTudo ? "Ver menos" : `Ver mais (${descobertas.length - 3})`}
                </Text>
              </TouchableOpacity>
            ) : null}
          </Card>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 16 }]}>
            São padrões que eu observei no seu histórico — não são regra pra todo mundo, e quanto
            mais você registra, mais coisa eu consigo cruzar.
          </Text>
        </View>
      ) : null}
    </View>
  );
}

function CoachingHub({
  order,
  onReorder,
  onDragStateChange,
  editMode,
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
  editMode: boolean;
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
  const meta = GOAL_META[analysis.goal ?? ""] ?? { label: "Seu objetivo", icon: "compass-outline" as const };
  const semana = semanaLabel(analysis.metrics.baseline_at);

  const rank = (i: CoachingInsight) => (i.adjustment ? 0 : 10) + (i.severity === "action" ? 0 : 1);
  const missoes = analysis.insights.filter((i) => i.severity !== "info").sort((a, b) => rank(a) - rank(b));
  const ok = analysis.insights.filter((i) => i.severity === "info");

  const streak = consistency?.current_streak ?? 0;
  const best = consistency?.best_streak ?? 0;
  const semConstancia = streak === 0 && best === 0;

  const pace = analysis.metrics.pace;
  const alvo = pace?.target_weight_kg ?? null;
  const atual = pace?.current_weight_kg ?? analysis.metrics.weight_kg ?? null;
  const inicial = pace?.start_weight_kg ?? null;
  const faltam = alvo != null && atual != null ? atual - alvo : null;

  const workout = analysis.metrics.workout;

  // Cada bloco é montado uma vez aqui; a ORDEM em que aparecem na tela vem de
  // `order` (editável em Configurações > Layout da tela inicial). Blocos
  // condicionais retornam null quando não há o que mostrar.
  const blocks: Record<HomeBlockId, React.ReactNode> = {
    hero: (
      <HeroCoaching
        meta={meta}
        semana={semana}
        alvo={alvo}
        atual={atual}
        inicial={inicial}
        faltam={faltam}
        streak={streak}
        best={best}
        semConstancia={semConstancia}
        onOpenChart={onOpenChart}
      />
    ),

    missoes: (
      <View style={{ marginBottom: spacing.md }}>
        {/* MISSÕES DA SEMANA — o que fazer agora. */}
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase", marginBottom: spacing.sm }]}>
          {missoes.length > 0 ? `Missões da semana · ${missoes.length}` : "Missões da semana"}
        </Text>
        {missoes.length > 0 ? (
          missoes.map((ins) => (
            <InsightBar
              key={ins.key}
              ins={ins}
              onApplied={onApplied}
              onOpenChart={onOpenChart}
              onOpenSection={onOpenSection}
            />
          ))
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

    aprendizado: <AprendizadoBlock learned={analysis.metrics.learned} />,

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
              icon: "barbell-outline",
              title: "Treino",
              subtitle: workout?.built ? `${workout.count} treino${workout.count === 1 ? "" : "s"}` : "Montar treino",
              onPress: onOpenTrainingModule,
            },
            {
              icon: "restaurant-outline",
              title: "Dieta",
              subtitle: analysis.metrics.goal_kcal ? `${Math.round(analysis.metrics.goal_kcal)} kcal/dia` : "Definir meta",
              onPress: onOpenDietModule,
            },
            { icon: "scale-outline", title: "Peso", subtitle: "Registrar e evolução", onPress: onOpenWeight },
            { icon: "moon-outline", title: "Sono", subtitle: "Noites e recuperação", onPress: onOpenSleep },
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
      editMode={editMode}
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
  onOpenTraining,
  onOpenDiary,
  onOpenTemplates,
  onOpenMeasurements,
  onAskCoach,
  onScrollTop,
}: {
  section: CoachingSectionId;
  analysis: CoachingAnalysis;
  changes: CoachingChange[];
  onBack: () => void;
  onApplied: (title: string, message: string) => void;
  progressMetric: CoachingChart;
  onProgressMetric: (m: CoachingChart) => void;
  onReload: () => void;
  onOpenTraining: () => void;
  onOpenDiary: () => void;
  onOpenTemplates: () => void;
  onOpenMeasurements: () => void;
  onAskCoach: () => void;
  onScrollTop: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const m = analysis.metrics;

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

      {/* A aba Objetivo é o centro do Coaching: questionário, resumo, edição
          das respostas, alterações pendentes e histórico de planos (spec §3).
          Ajuste pós-v36 (item 1/2): sem card duplicado por cima — ela já traz
          seu próprio "Seu objetivo atual", sem repetir a mesma informação em
          dois lugares. "Ver dieta em PDF" abre a dieta PERSONALIZADA (montada
          do questionário) num modal interno — nunca as dietas prontas, que
          ficam só na aba Dieta. */}
      {section === "objetivo" ? (
        <ObjectiveScreen onScrollTop={onScrollTop} onPlanActivated={onReload} />
      ) : null}

      {/* "Como eu monto seu treino" saiu daqui também (spec §5.1): a coleta
          agora é uma só, na aba Objetivo. Manter uma segunda cópia editável
          das mesmas preferências era exatamente o problema que a spec resolve
          — duas fontes da verdade discordando. */}
      {section === "treino" ? (
        <WorkoutCard workout={m.workout} onApplied={onApplied} onOpenTraining={onOpenTraining} />
      ) : null}

      {/* "Sua meta atual" saiu daqui (ajuste pós-v36, item 2): quem quiser ver
          ou mudar a meta vai na aba Objetivo — evita duas fontes da mesma
          informação. */}
      {section === "dieta" ? (
        <>
          <CoachRow icon="book" tint={colors.moduleNutrition} title="Abrir meu diário" subtitle="Registrar refeições e água de hoje" onPress={onOpenDiary} />
          <CoachRow icon="sparkles" tint={colors.primary} title="Gerar dieta com o coach" subtitle="Um cardápio na sua meta, em segundos" onPress={onAskCoach} />
          <CoachRow icon="restaurant-outline" tint={colors.moduleTraining} title="Dietas prontas" subtitle="Cardápios prontos pra adaptar" onPress={onOpenTemplates} />
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
            {b.chart ? <Ionicons name="stats-chart-outline" size={13} color={colors.textSecondary} /> : null}
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
  onOpenSection,
}: {
  ins: CoachingInsight;
  onApplied: (title: string, message: string) => void;
  onOpenChart: (chart: CoachingChart) => void;
  onOpenSection?: (s: CoachingSectionId) => void;
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
  // Bloco de especialização vencido: três saídas legítimas, sem uma
  // "recomendada" — a decisão é da pessoa, e o coach já disse o custo no texto.
  const podeRevisarEspecializacao = kind === "specialization" && !!ins.finding_key;
  const semanasDoProximoBloco = ins.adjustment?.block_weeks ?? 6;
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

  async function decidirEspecializacao(escolha: "keep" | "end") {
    setErro(null);
    setApplying(true);
    try {
      const r = await applyCoachAction(`specialization:${escolha}`);
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
            <Ionicons name="stats-chart-outline" size={15} color={colors.textSecondary} />
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
                  : "A carga já vem pré-preenchida na próxima vez que você treinar esse exercício. Dá pra desfazer."}
              </Text>
            </>
          )}
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: 4, textAlign: "center" }]}>{erro}</Text>
          ) : null}
        </View>
      ) : podeRevisarEspecializacao ? (
        <View style={{ marginTop: spacing.sm, gap: spacing.sm }}>
          {/* Três saídas de MESMO peso visual, de propósito: qual delas é a
              certa depende do objetivo da pessoa, não do app. O coach já disse
              o custo no texto acima — aqui ele para de opinar. */}
          <Button
            title={`Seguir mais ${semanasDoProximoBloco} semanas`}
            variant="secondary"
            compact
            loading={applying}
            onPress={() => decidirEspecializacao("keep")}
          />
          <Button
            title="Trocar de prioridade"
            variant="secondary"
            compact
            disabled={applying}
            onPress={() => onOpenSection?.("treino")}
          />
          <Button
            title="Voltar todo mundo ao normal"
            variant="secondary"
            compact
            loading={applying}
            onPress={() => decidirEspecializacao("end")}
          />
          <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center" }]}>
            Voltar ao normal remonta seu treino na hora. Seguir não muda nada — só adia a conversa.
          </Text>
          {erro ? (
            <Text style={[type.caption, { color: colors.warning, textAlign: "center" }]}>{erro}</Text>
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
          <Ionicons name="compass-outline" size={38} color={colors.primary} />
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
