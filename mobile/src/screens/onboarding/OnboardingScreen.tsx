import React, { useState } from "react";
import { Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { submitOnboarding, type OnboardingPayload } from "../../api/onboarding";
import { Button } from "../../components/Button";
import { HelpDot } from "../../components/HelpDot";
import { OptionButton } from "../../components/OptionButton";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

type FormState = Omit<OnboardingPayload, "age" | "height_cm" | "current_weight_kg"> & {
  age: string;
  height_cm: string;
  current_weight_kg: string;
  partner_handle: string;
};

// O onboarding coleta só o essencial para calcular a meta (Mifflin-St Jeor)
// + consentimento LGPD. Experiência, local de treino, dias, restrições e
// lesões ficam com padrões sensatos e podem ser ajustados depois no perfil —
// isso reduz drasticamente o abandono na primeira tela.
const initialForm: FormState = {
  biological_sex: "female",
  age: "",
  height_cm: "",
  current_weight_kg: "",
  activity_level: "moderate",
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

const TOTAL_STEPS = 7;

export function OnboardingScreen({ onDone }: { onDone?: () => void } = {}) {
  const { colors, type, spacing } = useTheme();
  const { refreshUser } = useAuth();
  const insets = useSafeAreaInsets();

  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
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
        return !!form.goal;
      case 5:
        return !!form.activity_level;
      case 6:
        return form.accepted_lgpd_health_data && form.accepted_medical_disclaimer;
      default:
        return true;
    }
  }

  async function handleFinish() {
    setIsSubmitting(true);
    try {
      // Só o envio no try. O refreshUser() ficava aqui e, se falhasse, o catch
      // mandava a pessoa refazer o onboarding INTEIRO — com o cadastro já
      // salvo no servidor.
      await submitOnboarding({
        ...form,
        age: Number(form.age),
        height_cm: Number(form.height_cm),
        current_weight_kg: Number(form.current_weight_kg),
        injuries_limitations: null,
        partner_handle: null,
      });
    } catch (err: any) {
      Alert.alert(
        "Não foi possível concluir o onboarding",
        mensagemDeErro(err, "Tente novamente em instantes.")
      );
      setIsSubmitting(false);
      return;
    }
    // Já cadastrado. O refresh atualiza o usuário; quando usado como gate, é o
    // que troca pro app. Como fluxo sob demanda (definir objetivo no Coaching),
    // o onDone recarrega a tela que chamou.
    await refreshUser().catch(() => {});
    setIsSubmitting(false);
    onDone?.();
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
          <Step title="Qual é o seu sexo biológico?" subtitle="É rápido — leva menos de um minuto. Usamos isso para calcular seu gasto calórico.">
            <OptionButton label="Feminino" selected={form.biological_sex === "female"} onPress={() => update("biological_sex", "female")} />
            <OptionButton label="Masculino" selected={form.biological_sex === "male"} onPress={() => update("biological_sex", "male")} />
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
          <Step title="Qual seu peso atual?" subtitle="Você atualiza quando quiser — cada registro fica salvo no seu histórico.">
            <NumberInput value={form.current_weight_kg} onChangeText={(v) => update("current_weight_kg", v)} suffix="kg" />
          </Step>
        );
      case 4:
        return (
          <Step
            title="Qual seu objetivo principal?"
            help={{
              title: "Qual escolher?",
              text:
                "Emagrecimento: perder gordura. Hipertrofia: ganhar músculo. Manutenção: manter o corpo atual. " +
                "Performance: melhorar força/rendimento. Recomposição: perder gordura e ganhar músculo ao mesmo tempo.",
            }}
          >
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
      case 5:
        return (
          <Step
            title="Como é seu dia a dia fora do treino?"
            help={{
              title: "Nível de atividade",
              text:
                "Sem contar o treino. Sedentário: trabalho sentado. Leve: caminha um pouco. Moderado: em pé/movendo com frequência. " +
                "Ativo/Muito ativo: trabalho físico ou muito movimento.",
            }}
          >
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
      case 6:
        return (
          <Step title="Quase lá!" subtitle="Só falta o consentimento. Experiência de treino, local e restrições você ajusta depois no perfil.">
            {/* Um único consentimento cobre as duas autorizações (uso de dados
                de saúde pela LGPD + ciência de que não substitui médico) — ambos
                continuam registrados no backend, mas a pessoa marca uma vez só. */}
            <ConsentRow
              checked={form.accepted_lgpd_health_data && form.accepted_medical_disclaimer}
              onToggle={() => {
                const next = !(form.accepted_lgpd_health_data && form.accepted_medical_disclaimer);
                update("accepted_lgpd_health_data", next);
                update("accepted_medical_disclaimer", next);
              }}
              text="Autorizo o uso dos meus dados de saúde (peso, altura, treino, alimentação) para personalizar o app, conforme a LGPD, e entendo que o Atlas não substitui acompanhamento médico ou nutricional profissional."
            />
          </Step>
        );
      default:
        return null;
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.xl + spacing.sm }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.xs }}>
          <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>
            Passo {step + 1} de {TOTAL_STEPS}
          </Text>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            {Math.round(((step + 1) / TOTAL_STEPS) * 100)}%
          </Text>
        </View>
        <View style={{ height: 6, backgroundColor: colors.border, borderRadius: 3 }}>
          <View
            style={{
              height: 6,
              width: `${((step + 1) / TOTAL_STEPS) * 100}%`,
              backgroundColor: colors.primary,
              borderRadius: 3,
            }}
          />
        </View>
      </View>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, flexGrow: 1 }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        {renderStep()}
      </ScrollView>
      <View style={{ flexDirection: "row", gap: spacing.sm, padding: spacing.lg, paddingBottom: spacing.lg + insets.bottom }}>
        {step > 0 ? (
          <View style={{ flex: 1 }}>
            <Button title="Voltar" variant="ghost" onPress={() => setStep((s) => s - 1)} />
          </View>
        ) : null}
        <View style={{ flex: 2 }}>
          <Button
            title={step === TOTAL_STEPS - 1 ? "Começar" : "Continuar"}
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
  help,
  children,
}: {
  title: string;
  subtitle?: string;
  help?: { title: string; text: string };
  children: React.ReactNode;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
        <Text style={[type.h1, { color: colors.textPrimary, flex: 1 }]}>{title}</Text>
        {help ? <HelpDot title={help.title} text={help.text} /> : null}
      </View>
      {subtitle ? (
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>{subtitle}</Text>
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
        onChangeText={(v) => onChangeText(v.replace(/,/g, ".").replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        autoFocus
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
      <Text style={[type.body, { color: colors.textSecondary, marginLeft: spacing.sm }]}>{suffix}</Text>
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
    <Pressable
      onPress={onToggle}
      style={{
        flexDirection: "row",
        alignItems: "flex-start",
        backgroundColor: checked ? colors.primarySoft : colors.surface,
        borderWidth: 1.5,
        borderColor: checked ? colors.primary : colors.border,
        borderRadius: radius.button,
        padding: spacing.md,
        marginBottom: spacing.md,
      }}
    >
      <View
        style={{
          width: 24,
          height: 24,
          borderRadius: 8,
          borderWidth: 2,
          borderColor: checked ? colors.primary : colors.border,
          backgroundColor: checked ? colors.primary : "transparent",
          alignItems: "center",
          justifyContent: "center",
          marginRight: spacing.sm,
        }}
      >
        {checked ? <Text style={{ color: colors.textOnPrimary, fontSize: 14, fontWeight: "800" }}>✓</Text> : null}
      </View>
      <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>{text}</Text>
    </Pressable>
  );
}
