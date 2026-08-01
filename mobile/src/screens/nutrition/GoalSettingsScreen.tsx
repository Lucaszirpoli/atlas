import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  applyAutoGoal,
  applyManualGoal,
  getCurrentGoal,
  type CalorieGoal,
} from "../../api/goals";
import {
  getProfileCalc,
  updateProfileCalc,
  type ActivityLevel,
  type BiologicalSex,
  type Goal,
  type ProfileCalc,
} from "../../api/profile";
import { getGoalPace, resetCoachingBaseline, type GoalPaceBlock } from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { HelpDot } from "../../components/HelpDot";
import { PaceSelector } from "../../components/PaceSelector";
import { useAuth } from "../../context/AuthContext";
import { voltarPara } from "../../navigation/voltarPara";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

const GOAL_OPTIONS: [Goal, string][] = [
  ["emagrecimento", "Emagrecimento"],
  ["hipertrofia", "Hipertrofia"],
  ["manutencao", "Manutenção"],
  ["performance", "Performance"],
  ["recomposicao", "Recomposição"],
];

const GOAL_LABEL: Record<string, string> = Object.fromEntries(GOAL_OPTIONS);

// Densidade energética de cada macro — a conversão de % pra gramas.
const KCAL_PER_G = { protein: 4, carbs: 4, fat: 9 } as const;

type MacroSplit = {
  kcal: number;
  pProt: number;
  pCarb: number;
  pFat: number;
  soma: number;
  /** Distância pra 100: positivo = falta, negativo = excede, 0 = fecha. */
  restante: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
  kcalValida: boolean;
  fecha100: boolean;
  podeSalvar: boolean;
};

/** Divisão em % da meta vigente, derivada dos gramas. Arredondar cada macro
 * separadamente às vezes fecha em 99 ou 101 — nesse caso a sobra vai pro maior
 * macro, pra tela não abrir já acusando "faltam 1%" numa meta que está certa. */
function percentuaisDaMeta(g: CalorieGoal): [number, number, number] {
  const pct = (gramas: number, kcalPorG: number) => Math.round(((gramas * kcalPorG) / g.kcal) * 100);
  const vals: [number, number, number] = [
    pct(g.protein_g, KCAL_PER_G.protein),
    pct(g.carbs_g, KCAL_PER_G.carbs),
    pct(g.fat_g, KCAL_PER_G.fat),
  ];
  const sobra = 100 - (vals[0] + vals[1] + vals[2]);
  if (sobra !== 0 && Math.abs(sobra) <= 2) {
    const maior = vals.indexOf(Math.max(...vals));
    vals[maior] += sobra;
  }
  return vals;
}

/** Converte "calorias + divisão em %" nos gramas de cada macro e diz se a
 * configuração é válida. Regra da spec §9.2: só salva quando P+C+G = 100%. */
function calcularSplit(kcalTxt: string, pProtTxt: string, pCarbTxt: string, pFatTxt: string): MacroSplit {
  const num = (t: string) => {
    const n = Number(String(t).replace(",", "."));
    return Number.isFinite(n) ? n : 0;
  };
  const kcal = Math.round(num(kcalTxt));
  const pProt = num(pProtTxt);
  const pCarb = num(pCarbTxt);
  const pFat = num(pFatTxt);
  const soma = Math.round((pProt + pCarb + pFat) * 10) / 10;
  const kcalValida = kcal >= 800 && kcal <= 8000;
  const fecha100 = soma === 100;
  return {
    kcal,
    pProt,
    pCarb,
    pFat,
    soma,
    restante: Math.round((100 - soma) * 10) / 10,
    proteinG: Math.round((kcal * pProt) / 100 / KCAL_PER_G.protein),
    carbsG: Math.round((kcal * pCarb) / 100 / KCAL_PER_G.carbs),
    fatG: Math.round((kcal * pFat) / 100 / KCAL_PER_G.fat),
    kcalValida,
    fecha100,
    podeSalvar: kcalValida && fecha100,
  };
}

const ACTIVITY_OPTIONS: [ActivityLevel, string][] = [
  ["sedentary", "Sedentário"],
  ["light", "Leve"],
  ["moderate", "Moderado"],
  ["active", "Ativo"],
  ["very_active", "Muito ativo"],
];

/** Ajuste pós-v36 (item 1): a meta calórica do Pro passou a morar só no
 * questionário da aba Objetivo — esta tela continua sendo o único jeito de
 * ajustar meta pro Free (que não tem aba Objetivo), mas o Pro vem parar aqui
 * de vários lugares antigos (histórico de navegação, favoritos) e precisa ver
 * pra onde foi, não um formulário duplicado. */
function ProRedirectCard() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg, paddingTop: spacing.xl + insets.top, alignItems: "center" }}>
      <View
        style={{
          width: 56, height: 56, borderRadius: 18, backgroundColor: colors.primary + "1F",
          alignItems: "center", justifyContent: "center", marginBottom: spacing.md,
        }}
      >
        <Ionicons name="compass-outline" size={28} color={colors.primary} />
      </View>
      <Text style={[type.h2, { color: colors.textPrimary, textAlign: "center" }]}>
        Isso agora fica na aba Objetivo
      </Text>
      <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 20 }]}>
        Automática ou manual, sua meta calórica se define junto do resto do seu questionário — pra tudo ficar
        num lugar só.
      </Text>
      <View style={{ marginTop: spacing.lg, alignSelf: "stretch" }}>
        {/* Home está no stack PAI (o de nutrição fica dentro dele). `navigate`
            empilharia uma segunda Home em cima de tudo; voltarPara desempilha
            até a que já existe. */}
        <Button
          title="Ir pra aba Objetivo"
          onPress={() => voltarPara(navigation, "Home", { section: "objetivo" })}
        />
      </View>
    </View>
  );
}

export function GoalSettingsScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const insets = useSafeAreaInsets();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  const [currentGoal, setCurrentGoal] = useState<CalorieGoal | null>(null);
  const [profile, setProfile] = useState<ProfileCalc | null>(null);
  // Ritmo do objetivo (Pro) — mora aqui, junto do cálculo automático (o ritmo
  // escala o déficit/superávit). null = não se aplica (manutenção/performance).
  const [pace, setPace] = useState<GoalPaceBlock | null>(null);
  // Prompt "recomeçar análise do coach" ao trocar de objetivo (só Pro tem coach).
  const [baselinePrompt, setBaselinePrompt] = useState<{ from: string; to: string } | null>(null);

  // Campos editáveis do cálculo automático (string pra permitir edição livre).
  const [sex, setSex] = useState<BiologicalSex>("female");
  const [age, setAge] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [goal, setGoal] = useState<Goal>("hipertrofia");
  const [activity, setActivity] = useState<ActivityLevel>("moderate");

  // Meta manual: a pessoa define as CALORIAS e a divisão dos macros em
  // PORCENTAGEM (não em gramas). Porcentagem é como todo mundo pensa a dieta
  // ("40/30/30") e é auto-verificável: se não fecha 100%, está errado. Os
  // gramas saem daí sozinhos (4 kcal/g proteína e carbo, 9 kcal/g gordura).
  const [manualKcal, setManualKcal] = useState("");
  const [pctProtein, setPctProtein] = useState("30");
  const [pctCarbs, setPctCarbs] = useState("45");
  const [pctFat, setPctFat] = useState("25");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // "Considerar como primeiro objetivo": vai direto pra meta nova (sem transição
  // gradual) e faz o coach esquecer a fase anterior. Pra trocar de fase de vez
  // (ex: encerrar o cutting e começar o bulking do zero).
  const [asFirstObjective, setAsFirstObjective] = useState(false);
  const mudouObjetivo = !!profile && profile.goal !== goal;
  const macroSplit = calcularSplit(manualKcal, pctProtein, pctCarbs, pctFat);

  async function load() {
    setIsLoading(true);
    try {
      const [goalNow, prof, paceNow] = await Promise.all([
        getCurrentGoal(),
        getProfileCalc().catch(() => null),
        isPro ? getGoalPace().catch(() => null) : Promise.resolve(null),
      ]);
      setCurrentGoal(goalNow);
      setPace(paceNow);
      // Abre o bloco manual já com a divisão ATUAL da pessoa (derivada dos
      // gramas da meta vigente), não com um padrão genérico — assim ela ajusta
      // o que tem em vez de recomeçar do zero.
      if (goalNow?.kcal) {
        setManualKcal(String(Math.round(goalNow.kcal)));
        const [p, c, g] = percentuaisDaMeta(goalNow);
        setPctProtein(String(p));
        setPctCarbs(String(c));
        setPctFat(String(g));
      }
      if (prof) {
        setProfile(prof);
        setSex(prof.biological_sex);
        setAge(String(prof.age));
        setHeightCm(String(Math.round(prof.height_cm)));
        setWeightKg(prof.current_weight_kg != null ? String(prof.current_weight_kg) : "");
        setGoal(prof.goal);
        setActivity(prof.activity_level);
      }
    } finally {
      setIsLoading(false);
    }
  }

  // Trocar o ritmo já recalcula a meta no backend — recarrega só a meta e o
  // ritmo, sem tocar nos campos que a pessoa possa estar editando acima.
  async function reloadPaceAndGoal() {
    const [g, p] = await Promise.all([
      getCurrentGoal().catch(() => null),
      getGoalPace().catch(() => null),
    ]);
    if (g) setCurrentGoal(g);
    setPace(p);
  }

  useEffect(() => {
    if (!isPro) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleApplyAuto() {
    const ageN = Number(age);
    const heightN = Number(heightCm);
    const weightN = Number(weightKg.replace(",", "."));
    if (!ageN || ageN < 13 || ageN > 100) {
      Alert.alert("Idade inválida", "Informe uma idade entre 13 e 100 anos.");
      return;
    }
    if (!heightN || heightN < 100 || heightN > 250) {
      Alert.alert("Altura inválida", "Informe a altura em cm (entre 100 e 250).");
      return;
    }
    if (!weightN || weightN < 30 || weightN > 300) {
      Alert.alert("Peso inválido", "Informe um peso entre 30 e 300 kg.");
      return;
    }
    const objetivoAnterior = profile?.goal;
    const trocou = !!objetivoAnterior && objetivoAnterior !== goal;
    // "Primeiro objetivo" só faz sentido quando muda de objetivo.
    const comoPrimeiro = asFirstObjective && trocou;
    setIsSubmitting(true);
    try {
      // 1) salva os dados no perfil (peso vira um novo registro no histórico)
      await updateProfileCalc({
        biological_sex: sex,
        age: ageN,
        height_cm: heightN,
        goal,
        activity_level: activity,
        current_weight_kg: weightN,
      });
      // 2) recalcula e aplica a meta a partir dos dados atualizados
      setCurrentGoal(await applyAutoGoal(comoPrimeiro));
      setProfile((p) => (p ? { ...p, goal } : p)); // reflete o novo objetivo
      setAsFirstObjective(false); // reseta o toggle após aplicar
      if (isPro) getGoalPace().then(setPace).catch(() => {}); // ritmo muda com o objetivo
      // Com "primeiro objetivo" o backend já recomeçou a análise (sem transição);
      // não precisa perguntar. Senão, se trocou de objetivo e é Pro, oferece
      // recomeçar a análise (ConfirmDialog — Alert.alert é no-op no web).
      if (comoPrimeiro) {
        Alert.alert("Novo objetivo", "Meta ajustada direto pro novo objetivo e análise recomeçada.");
      } else if (trocou && isPro) {
        setBaselinePrompt({ from: GOAL_LABEL[objetivoAnterior!] ?? objetivoAnterior!, to: GOAL_LABEL[goal] ?? goal });
      } else {
        Alert.alert("Meta atualizada", "Sua meta calórica foi recalculada com seus dados.");
      }
    } catch (err: any) {
      Alert.alert("Não foi possível calcular", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function confirmarResetCoach() {
    try {
      await resetCoachingBaseline();
    } catch {
      // silencioso — não é destrutivo; a análise só não recomeça
    }
  }

  async function handleApplyManual() {
    if (!macroSplit.podeSalvar) return;
    setIsSubmitting(true);
    try {
      setCurrentGoal(
        await applyManualGoal({
          kcal: macroSplit.kcal,
          protein_g: macroSplit.proteinG,
          carbs_g: macroSplit.carbsG,
          fat_g: macroSplit.fatG,
        })
      );
      Alert.alert("Meta salva", "Sua meta manual foi definida.");
    } catch (err: any) {
      Alert.alert("Não foi possível salvar", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isPro) {
    return <ProRedirectCard />;
  }

  if (isLoading) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl + insets.bottom }}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
      {/* Meta atual — compacta (uma linha), pra sobrar espaço pros campos do
          cálculo automático abaixo. */}
      {currentGoal ? (
        <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="flag" size={16} color={colors.primary} />
            <Text style={[type.caption, { color: colors.textSecondary, marginLeft: 6, flex: 1 }]}>
              META ATUAL · {currentGoal.mode === "auto" ? "AUTOMÁTICA" : "MANUAL"}
            </Text>
            <Text style={[type.h2, { color: colors.textPrimary }]}>
              {Math.round(currentGoal.kcal)}
              <Text style={[type.caption, { color: colors.textSecondary }]}> kcal</Text>
            </Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm }}>
            <MacroChip label="P" value={currentGoal.protein_g} color={colors.moduleTraining} />
            <MacroChip label="C" value={currentGoal.carbs_g} color={colors.info} />
            <MacroChip label="G" value={currentGoal.fat_g} color={colors.warning} />
            <HelpDot
              title="Macros (P, C, G)"
              text={
                "P = proteína (constrói e mantém músculo), C = carboidrato (principal fonte de energia), " +
                "G = gordura (hormônios e saúde geral). A meta em gramas por dia de cada um compõe suas calorias totais."
              }
            />
          </View>
        </Card>
      ) : null}

      {/* Cálculo automático — agora com os dados editáveis aqui mesmo. */}
      <Card style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
          <Ionicons name="calculator" size={18} color={colors.primary} />
          <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1 }]}>Cálculo automático</Text>
          <HelpDot
            title="Como é calculado?"
            text={
              "Usamos a fórmula Mifflin-St Jeor, a mais precisa reconhecida hoje: ela estima quanto seu corpo " +
              "gasta em repouso a partir de peso, altura, idade e sexo. Depois multiplicamos pelo seu nível de " +
              "atividade e ajustamos pro seu objetivo (déficit pra emagrecer, superávit pra ganhar massa)."
            }
          />
        </View>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
          Confira ou ajuste seus dados e toque em "Usar cálculo automático".
        </Text>

        {/* Sexo biológico */}
        <FieldLabel text="Sexo biológico" />
        <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
          <Chip label="Feminino" selected={sex === "female"} onPress={() => setSex("female")} flex />
          <Chip label="Masculino" selected={sex === "male"} onPress={() => setSex("male")} flex />
        </View>

        {/* Idade / Altura / Peso */}
        <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
          <NumField label="Idade" value={age} onChangeText={setAge} suffix="anos" />
          <NumField label="Altura" value={heightCm} onChangeText={setHeightCm} suffix="cm" />
          <NumField label="Peso" value={weightKg} onChangeText={setWeightKg} suffix="kg" decimal />
        </View>

        {/* Objetivo */}
        <FieldLabel text="Objetivo" />
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: mudouObjetivo ? spacing.sm : spacing.md }}>
          {GOAL_OPTIONS.map(([value, label]) => (
            <Chip key={value} label={label} selected={goal === value} onPress={() => setGoal(value)} />
          ))}
        </View>

        {/* "Considerar como primeiro objetivo" — só quando muda de objetivo.
            Pula a transição gradual e faz o coach esquecer a fase anterior. */}
        {mudouObjetivo ? (
          <TouchableOpacity
            onPress={() => setAsFirstObjective((v) => !v)}
            activeOpacity={0.7}
            style={{
              flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.md,
              backgroundColor: colors.surfaceAlt, borderRadius: radius.button, padding: spacing.sm,
              borderWidth: 1, borderColor: asFirstObjective ? colors.primary : colors.border,
            }}
          >
            <Ionicons
              name={asFirstObjective ? "checkbox" : "square-outline"}
              size={20}
              color={asFirstObjective ? colors.primary : colors.textSecondary}
            />
            <View style={{ flex: 1 }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
                Considerar como primeiro objetivo
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1, lineHeight: 16 }]}>
                Vai direto pra nova meta, sem subir/descer as calorias aos poucos. O coach esquece a fase anterior
                (ideal pra encerrar um cutting e começar o bulking do zero).
              </Text>
            </View>
          </TouchableOpacity>
        ) : null}

        {/* Nível de atividade */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
          <FieldLabel text="Nível de atividade (fora do treino)" />
          <HelpDot
            title="Nível de atividade"
            text={
              "Sem contar o treino. Sedentário: trabalho sentado. Leve: caminha um pouco. Moderado: em pé/movendo " +
              "com frequência. Ativo/Muito ativo: trabalho físico ou muito movimento."
            }
          />
        </View>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.md }}>
          {ACTIVITY_OPTIONS.map(([value, label]) => (
            <Chip key={value} label={label} selected={activity === value} onPress={() => setActivity(value)} />
          ))}
        </View>

        {/* Ritmo do objetivo (Pro) — devagar/normal/rápido. Escala o déficit/
            superávit e aplica na hora. Só quando o ritmo se aplica ao objetivo. */}
        {isPro && pace && pace.options.length > 0 ? (
          <View style={{ borderTopWidth: 1, borderTopColor: colors.border, marginTop: spacing.xs, marginBottom: spacing.md }}>
            <PaceSelector pace={pace} onChanged={reloadPaceAndGoal} />
          </View>
        ) : null}

        <Button title="Usar cálculo automático" onPress={handleApplyAuto} loading={isSubmitting} />
      </Card>

      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Ou defina manualmente
      </Text>
      <Card>
        <FieldLabel text="Calorias por dia" />
        <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
          <ManualInput label="kcal" value={manualKcal} onChangeText={setManualKcal} />
          <View style={{ flex: 2, justifyContent: "flex-end", paddingBottom: 4 }}>
            <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 16 }]}>
              Você define as calorias; a divisão dos macros vai em porcentagem abaixo.
            </Text>
          </View>
        </View>

        <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginBottom: spacing.xs }}>
          <FieldLabel text="Divisão dos macros (%)" />
          <HelpDot
            title="Por que porcentagem?"
            text={
              "É como as dietas são descritas ('40/30/30') e dá pra conferir na hora: se não soma 100%, tem algo " +
              "errado. Os gramas saem sozinhos das calorias — proteína e carboidrato rendem 4 kcal por grama, " +
              "gordura rende 9."
            }
          />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <PercentInput label="Proteína" value={pctProtein} onChangeText={setPctProtein} grams={macroSplit.proteinG} tint={colors.moduleTraining} />
          <PercentInput label="Carbo" value={pctCarbs} onChangeText={setPctCarbs} grams={macroSplit.carbsG} tint={colors.info} />
          <PercentInput label="Gordura" value={pctFat} onChangeText={setPctFat} grams={macroSplit.fatG} tint={colors.warning} />
        </View>

        {/* Aviso PERMANENTE da regra + quanto falta/excede em tempo real. */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "flex-start",
            gap: 8,
            marginTop: spacing.md,
            backgroundColor: macroSplit.fecha100 ? colors.success + "14" : colors.warning + "14",
            borderRadius: radius.card,
            padding: spacing.sm,
          }}
        >
          <Ionicons
            name={macroSplit.fecha100 ? "checkmark-circle" : "alert-circle"}
            size={16}
            color={macroSplit.fecha100 ? colors.success : colors.warning}
            style={{ marginTop: 1 }}
          />
          <View style={{ flex: 1 }}>
            <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 17 }]}>
              A soma de proteína, carboidratos e gorduras deve totalizar 100%.
            </Text>
            <Text
              style={[
                type.bodySmall,
                {
                  color: macroSplit.fecha100 ? colors.success : colors.warning,
                  fontWeight: "800",
                  marginTop: 3,
                },
              ]}
            >
              {macroSplit.fecha100
                ? `${macroSplit.soma}% — configuração válida.`
                : macroSplit.restante > 0
                ? `Somando ${macroSplit.soma}% — faltam ${macroSplit.restante}%.`
                : `Somando ${macroSplit.soma}% — excede em ${Math.abs(macroSplit.restante)}%.`}
            </Text>
          </View>
        </View>

        {macroSplit.fecha100 && !macroSplit.kcalValida ? (
          <Text style={[type.caption, { color: colors.warning, marginTop: spacing.xs }]}>
            Informe as calorias do dia (entre 800 e 8000 kcal).
          </Text>
        ) : null}

        {macroSplit.podeSalvar ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, textAlign: "center" }]}>
            Vai ficar: {macroSplit.kcal} kcal · P {macroSplit.proteinG}g · C {macroSplit.carbsG}g · G{" "}
            {macroSplit.fatG}g
          </Text>
        ) : null}

        <View style={{ marginTop: spacing.md }}>
          <Button
            title="Salvar meta manual"
            variant="ghost"
            onPress={handleApplyManual}
            loading={isSubmitting}
            disabled={!macroSplit.podeSalvar}
          />
        </View>
      </Card>

      <ConfirmDialog
        visible={!!baselinePrompt}
        onClose={() => setBaselinePrompt(null)}
        title="Recomeçar a análise do coach?"
        message={
          baselinePrompt
            ? `Você trocou de ${baselinePrompt.from} pra ${baselinePrompt.to}. Recomeço a análise a partir de agora pra ela não misturar a fase anterior? Seu histórico e gráficos continuam intactos.`
            : undefined
        }
        confirmLabel="Recomeçar análise"
        onConfirm={confirmarResetCoach}
      />
    </ScrollView>
  );
}

function FieldLabel({ text }: { text: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{text}</Text>
  );
}

function Chip({
  label,
  selected,
  onPress,
  flex,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  flex?: boolean;
}) {
  const { colors, type, radius, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      style={{
        flex: flex ? 1 : undefined,
        alignItems: "center",
        borderRadius: radius.pill,
        paddingVertical: spacing.sm,
        paddingHorizontal: spacing.md,
        backgroundColor: selected ? colors.primary : colors.surfaceAlt,
        borderWidth: 1.5,
        borderColor: selected ? colors.primary : colors.border,
      }}
    >
      <Text
        style={[
          type.bodySmall,
          { color: selected ? colors.textOnPrimary : colors.textPrimary, fontWeight: selected ? "700" : "500" },
        ]}
      >
        {label}
      </Text>
    </TouchableOpacity>
  );
}

function NumField({
  label,
  value,
  onChangeText,
  suffix,
  decimal,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  suffix: string;
  decimal?: boolean;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{label}</Text>
      <View style={{ flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceAlt, borderRadius: radius.button, paddingHorizontal: spacing.sm, height: 48 }}>
        <TextInput
          value={value}
          onChangeText={(v) => onChangeText(v.replace(decimal ? /[^0-9.,]/g : /[^0-9]/g, ""))}
          keyboardType={decimal ? "decimal-pad" : "number-pad"}
          style={[type.body, { flex: 1, minWidth: 0, color: colors.textPrimary, fontWeight: "600", textAlign: "center" }]}
        />
        <Text style={[type.caption, { color: colors.textSecondary }]}>{suffix}</Text>
      </View>
    </View>
  );
}

function MacroChip({ label, value, color }: { label: string; value: number; color: string }) {
  const { type, radius } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: color + "1A",
        borderRadius: radius.pill,
        paddingVertical: 4,
        paddingHorizontal: 12,
        gap: 4,
      }}
    >
      <Text style={[type.caption, { color, fontWeight: "800" }]}>{label}</Text>
      <Text style={[type.caption, { color, fontWeight: "600" }]}>{Math.round(value)}g</Text>
    </View>
  );
}

/** Campo de porcentagem de um macro, com os gramas resultantes logo abaixo —
 * a pessoa vê na hora o que a porcentagem vira no prato. */
function PercentInput({
  label,
  value,
  onChangeText,
  grams,
  tint,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  grams: number;
  tint: string;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 5, marginBottom: spacing.xs }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: tint }} />
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: colors.surfaceAlt,
          borderRadius: radius.button,
          height: 48,
          paddingHorizontal: spacing.xs,
        }}
      >
        <TextInput
          value={value}
          onChangeText={(v) => onChangeText(v.replace(/,/g, ".").replace(/[^0-9.]/g, "").slice(0, 5))}
          keyboardType="decimal-pad"
          selectTextOnFocus
          style={[
            type.body,
            { color: colors.textPrimary, fontWeight: "700", textAlign: "right", minWidth: 34, padding: 0 },
          ]}
        />
        <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>%</Text>
      </View>
      <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: 3 }]}>
        {grams}g
      </Text>
    </View>
  );
}

function ManualInput({
  label,
  value,
  onChangeText,
  flex = 1,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  flex?: number;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flex }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/,/g, ".").replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderRadius: radius.button,
            paddingHorizontal: spacing.sm,
            height: 48,
            backgroundColor: colors.surfaceAlt,
            textAlign: "center",
            fontWeight: "600",
          },
        ]}
      />
    </View>
  );
}
