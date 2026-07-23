import { Ionicons } from "@expo/vector-icons";
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

const ACTIVITY_OPTIONS: [ActivityLevel, string][] = [
  ["sedentary", "Sedentário"],
  ["light", "Leve"],
  ["moderate", "Moderado"],
  ["active", "Ativo"],
  ["very_active", "Muito ativo"],
];

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

  const [manualKcal, setManualKcal] = useState("");
  const [manualProtein, setManualProtein] = useState("");
  const [manualCarbs, setManualCarbs] = useState("");
  const [manualFat, setManualFat] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // "Considerar como primeiro objetivo": vai direto pra meta nova (sem transição
  // gradual) e faz o coach esquecer a fase anterior. Pra trocar de fase de vez
  // (ex: encerrar o cutting e começar o bulking do zero).
  const [asFirstObjective, setAsFirstObjective] = useState(false);
  const mudouObjetivo = !!profile && profile.goal !== goal;

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
    load();
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
    const kcal = Number(manualKcal);
    const protein = Number(manualProtein);
    const carbs = Number(manualCarbs);
    const fat = Number(manualFat);
    if (!kcal || !protein || !carbs || !fat) {
      Alert.alert("Preencha todos os campos", "Calorias, proteína, carboidrato e gordura são obrigatórios.");
      return;
    }
    setIsSubmitting(true);
    try {
      setCurrentGoal(await applyManualGoal({ kcal, protein_g: protein, carbs_g: carbs, fat_g: fat }));
      Alert.alert("Meta salva", "Sua meta manual foi definida.");
    } finally {
      setIsSubmitting(false);
    }
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
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <ManualInput label="kcal" value={manualKcal} onChangeText={setManualKcal} flex={1.2} />
          <ManualInput label="Prot (g)" value={manualProtein} onChangeText={setManualProtein} />
          <ManualInput label="Carb (g)" value={manualCarbs} onChangeText={setManualCarbs} />
          <ManualInput label="Gord (g)" value={manualFat} onChangeText={setManualFat} />
        </View>
        <View style={{ marginTop: spacing.md }}>
          <Button title="Salvar meta manual" variant="ghost" onPress={handleApplyManual} loading={isSubmitting} />
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
