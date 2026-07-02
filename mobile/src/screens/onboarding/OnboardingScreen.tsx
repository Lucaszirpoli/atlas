import React, { useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import { submitOnboarding, type OnboardingPayload } from "../../api/onboarding";
import { Button } from "../../components/Button";
import { OptionButton } from "../../components/OptionButton";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const WEEKDAYS = [
  { key: "mon", label: "Segunda" },
  { key: "tue", label: "Terça" },
  { key: "wed", label: "Quarta" },
  { key: "thu", label: "Quinta" },
  { key: "fri", label: "Sexta" },
  { key: "sat", label: "Sábado" },
  { key: "sun", label: "Domingo" },
];

const DIETARY_RESTRICTIONS = [
  "Vegetariano",
  "Vegano",
  "Low carb",
  "Sem glúten",
  "Sem lactose",
];

type FormState = Omit<OnboardingPayload, "age" | "height_cm" | "current_weight_kg"> & {
  age: string;
  height_cm: string;
  current_weight_kg: string;
  partner_handle: string;
};

const initialForm: FormState = {
  biological_sex: "female",
  age: "",
  height_cm: "",
  current_weight_kg: "",
  activity_level: "sedentary",
  goal: "hipertrofia",
  experience_level: "iniciante",
  training_location: "academia_completa",
  training_style_preference: "ia_decide",
  available_days: [],
  dietary_restrictions: [],
  injuries_limitations: null,
  preferred_advanced_technique: null,
  trains_with_partner: false,
  partner_handle: "",
  accepted_lgpd_health_data: false,
  accepted_medical_disclaimer: false,
};

const TOTAL_STEPS = 13;

export function OnboardingScreen() {
  const { colors, type, spacing } = useTheme();
  const { refreshUser } = useAuth();

  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleInArray(key: "available_days" | "dietary_restrictions", value: string) {
    setForm((prev) => {
      const current = prev[key];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      return { ...prev, [key]: next };
    });
  }

  function canProceed(): boolean {
    switch (step) {
      case 0:
        return !!form.biological_sex;
      case 1:
        return Number(form.age) >= 13 && Number(form.age) <= 100;
      case 2:
        return Number(form.height_cm) >= 100 && Number(form.height_cm) <= 250;
      case 3:
        return Number(form.current_weight_kg) >= 30 && Number(form.current_weight_kg) <= 300;
      case 4:
        return !!form.activity_level;
      case 5:
        return !!form.goal;
      case 6:
        return !!form.experience_level;
      case 7:
        return !!form.training_location;
      case 8:
        return form.available_days.length > 0;
      case 11:
        return !form.trains_with_partner || form.partner_handle.trim().length >= 3;
      case 12:
        return form.accepted_lgpd_health_data && form.accepted_medical_disclaimer;
      default:
        return true;
    }
  }

  async function handleFinish() {
    setIsSubmitting(true);
    try {
      await submitOnboarding({
        ...form,
        age: Number(form.age),
        height_cm: Number(form.height_cm),
        current_weight_kg: Number(form.current_weight_kg),
        injuries_limitations: form.injuries_limitations?.trim() || null,
        partner_handle: form.trains_with_partner ? form.partner_handle.trim() : null,
      });
      await refreshUser();
    } catch (err: any) {
      Alert.alert(
        "Não foi possível concluir o onboarding",
        err?.response?.data?.detail ?? "Tente novamente em instantes."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function goNext() {
    if (step === TOTAL_STEPS - 1) {
      handleFinish();
      return;
    }
    setStep((s) => s + 1);
  }

  function renderStep() {
    switch (step) {
      case 0:
        return (
          <Step title="Qual é o seu sexo biológico?" subtitle="Usamos isso para calcular seu gasto calórico com mais precisão.">
            <OptionButton
              label="Feminino"
              selected={form.biological_sex === "female"}
              onPress={() => update("biological_sex", "female")}
            />
            <OptionButton
              label="Masculino"
              selected={form.biological_sex === "male"}
              onPress={() => update("biological_sex", "male")}
            />
          </Step>
        );
      case 1:
        return (
          <Step title="Qual sua idade?">
            <NumberInput value={form.age} onChangeText={(v) => update("age", v)} suffix="anos" />
          </Step>
        );
      case 2:
        return (
          <Step title="Qual sua altura?">
            <NumberInput value={form.height_cm} onChangeText={(v) => update("height_cm", v)} suffix="cm" />
          </Step>
        );
      case 3:
        return (
          <Step title="Qual seu peso atual?" subtitle="Você poderá atualizar isso a qualquer momento — cada registro fica salvo no seu histórico.">
            <NumberInput
              value={form.current_weight_kg}
              onChangeText={(v) => update("current_weight_kg", v)}
              suffix="kg"
            />
          </Step>
        );
      case 4:
        return (
          <Step title="Como é seu nível de atividade fora do treino?">
            {[
              ["sedentary", "Sedentário"],
              ["light", "Leve"],
              ["moderate", "Moderado"],
              ["active", "Ativo"],
              ["very_active", "Muito ativo"],
            ].map(([value, label]) => (
              <OptionButton
                key={value}
                label={label}
                selected={form.activity_level === value}
                onPress={() => update("activity_level", value as FormState["activity_level"])}
              />
            ))}
          </Step>
        );
      case 5:
        return (
          <Step title="Qual seu objetivo principal?">
            {[
              ["emagrecimento", "Emagrecimento"],
              ["hipertrofia", "Hipertrofia"],
              ["manutencao", "Manutenção"],
              ["performance", "Performance"],
              ["recomposicao", "Recomposição"],
            ].map(([value, label]) => (
              <OptionButton
                key={value}
                label={label}
                selected={form.goal === value}
                onPress={() => update("goal", value as FormState["goal"])}
              />
            ))}
          </Step>
        );
      case 6:
        return (
          <Step title="Qual sua experiência de treino?">
            {[
              ["iniciante", "Iniciante"],
              ["intermediario", "Intermediário"],
              ["avancado", "Avançado"],
            ].map(([value, label]) => (
              <OptionButton
                key={value}
                label={label}
                selected={form.experience_level === value}
                onPress={() => update("experience_level", value as FormState["experience_level"])}
              />
            ))}
          </Step>
        );
      case 7:
        return (
          <Step title="Onde você treina?">
            {[
              ["academia_completa", "Academia completa"],
              ["academia_basica", "Academia básica"],
              ["casa_com_equipamento", "Casa com equipamento"],
              ["casa_sem_equipamento", "Casa sem equipamento"],
            ].map(([value, label]) => (
              <OptionButton
                key={value}
                label={label}
                selected={form.training_location === value}
                onPress={() => update("training_location", value as FormState["training_location"])}
              />
            ))}
          </Step>
        );
      case 8:
        return (
          <Step title="Quais dias você tem disponível para treinar?" subtitle="Escolha um ou mais.">
            {WEEKDAYS.map((day) => (
              <OptionButton
                key={day.key}
                label={day.label}
                selected={form.available_days.includes(day.key)}
                onPress={() => toggleInArray("available_days", day.key)}
              />
            ))}
          </Step>
        );
      case 9:
        return (
          <Step title="Alguma restrição alimentar?" subtitle="Opcional — pode pular se não tiver nenhuma.">
            {DIETARY_RESTRICTIONS.map((restriction) => (
              <OptionButton
                key={restriction}
                label={restriction}
                selected={form.dietary_restrictions.includes(restriction)}
                onPress={() => toggleInArray("dietary_restrictions", restriction)}
              />
            ))}
          </Step>
        );
      case 10:
        return (
          <Step
            title="Tem alguma lesão ou limitação física atual?"
            subtitle="Isso é importante para nunca sugerirmos um exercício perigoso pra você. Opcional."
          >
            <TextInput
              value={form.injuries_limitations ?? ""}
              onChangeText={(v) => update("injuries_limitations", v)}
              placeholder="Ex: dor no ombro direito, evitar agachamento profundo..."
              placeholderTextColor={colors.textSecondary}
              multiline
              style={{
                minHeight: 100,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: 8,
                padding: spacing.md,
                color: colors.textPrimary,
                textAlignVertical: "top",
              }}
            />
          </Step>
        );
      case 11:
        return (
          <Step title="Você treina com parceiro(a)?">
            <OptionButton
              label="Não"
              selected={!form.trains_with_partner}
              onPress={() => {
                update("trains_with_partner", false);
                update("partner_handle", "");
              }}
            />
            <OptionButton
              label="Sim"
              selected={form.trains_with_partner}
              onPress={() => update("trains_with_partner", true)}
            />
            {form.trains_with_partner ? (
              <TextInput
                value={form.partner_handle}
                onChangeText={(v) => update("partner_handle", v.toLowerCase())}
                placeholder="@handle do seu parceiro(a)"
                placeholderTextColor={colors.textSecondary}
                autoCapitalize="none"
                style={{
                  marginTop: spacing.sm,
                  height: 48,
                  borderWidth: 1,
                  borderColor: colors.border,
                  borderRadius: 8,
                  paddingHorizontal: spacing.md,
                  color: colors.textPrimary,
                }}
              />
            ) : null}
          </Step>
        );
      case 12:
        return (
          <Step title="Antes de continuar">
            <ConsentRow
              checked={form.accepted_lgpd_health_data}
              onToggle={() => update("accepted_lgpd_health_data", !form.accepted_lgpd_health_data)}
              text="Autorizo o uso dos meus dados de saúde (peso, altura, treino, alimentação) para personalizar o app, conforme a LGPD."
            />
            <ConsentRow
              checked={form.accepted_medical_disclaimer}
              onToggle={() => update("accepted_medical_disclaimer", !form.accepted_medical_disclaimer)}
              text="Entendo que o appfit não substitui acompanhamento médico ou nutricional profissional."
            />
          </Step>
        );
      default:
        return null;
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, flexGrow: 1 }}>
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
          Passo {step + 1} de {TOTAL_STEPS}
        </Text>
        {renderStep()}
      </ScrollView>
      <View style={{ flexDirection: "row", gap: spacing.sm, padding: spacing.lg }}>
        {step > 0 ? (
          <View style={{ flex: 1 }}>
            <Button title="Voltar" variant="ghost" onPress={() => setStep((s) => s - 1)} />
          </View>
        ) : null}
        <View style={{ flex: 2 }}>
          <Button
            title={step === TOTAL_STEPS - 1 ? "Concluir" : "Continuar"}
            onPress={goNext}
            disabled={!canProceed()}
            loading={isSubmitting}
          />
        </View>
      </View>
    </View>
  );
}

function Step({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.xs }]}>{title}</Text>
      {subtitle ? (
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
          {subtitle}
        </Text>
      ) : (
        <View style={{ marginBottom: spacing.sm }} />
      )}
      {children}
    </View>
  );
}

function NumberInput({
  value,
  onChangeText,
  suffix,
}: {
  value: string;
  onChangeText: (v: string) => void;
  suffix: string;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center" }}>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.display,
          {
            color: colors.textPrimary,
            borderBottomWidth: 2,
            borderBottomColor: colors.primary,
            minWidth: 100,
            paddingVertical: spacing.xs,
          },
        ]}
      />
      <Text style={[type.body, { color: colors.textSecondary, marginLeft: spacing.sm }]}>
        {suffix}
      </Text>
    </View>
  );
}

function ConsentRow({
  checked,
  onToggle,
  text,
}: {
  checked: boolean;
  onToggle: () => void;
  text: string;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "flex-start",
        marginBottom: spacing.md,
      }}
    >
      <OptionButton label={checked ? "✓" : " "} selected={checked} onPress={onToggle} />
      <Text
        style={[
          type.bodySmall,
          { color: colors.textPrimary, flex: 1, marginLeft: spacing.sm, marginTop: spacing.sm },
        ]}
        onPress={onToggle}
      >
        {text}
      </Text>
    </View>
  );
}
