import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getDietContext, type DietContext } from "../../api/ai";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

// Pedido pronto que a IA recebe ao abrir o chat pela "dieta personalizada".
const DIET_AI_PROMPT =
  "Quero que você monte uma dieta personalizada pra mim. Me pergunte o que precisar — " +
  "minhas restrições alimentares, quantas refeições por dia eu prefiro, o que eu gosto e o que " +
  "não gosto de comer. Depois monte a dieta do dia inteiro batendo minha meta de calorias e macros.";

function MacroPill({ label, value, unit, color }: { label: string; value: number | null; unit: string; color: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ alignItems: "center", flex: 1 }}>
      <Text style={[type.h2, { color, fontSize: 18 }]}>{value != null ? Math.round(value) : "—"}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, fontSize: 10 }]}>
        {label}
        {unit}
      </Text>
    </View>
  );
}

/** Hub de "montar dieta". Todo mundo vê a meta diária e as dietas prontas
 * (grátis). "Gerar minha dieta personalizada" é do Pro: leva ao chat da IA, que
 * pergunta restrições/refeições/gostos e monta — Free vê o botão mas cai no
 * paywall ao tocar (mesma lógica do treino). */
export function AiDietScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  const [ctx, setCtx] = useState<DietContext | null>(null);

  useEffect(() => {
    getDietContext()
      .then(setCtx)
      .catch(() => {});
  }, []);

  function handlePersonalized() {
    if (!isPro) {
      navigation.navigate("Paywall");
      return;
    }
    navigation.navigate("Assistant", { autoSend: DIET_AI_PROMPT });
  }

  const noGoal = ctx != null && ctx.target_kcal == null;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
    >
      <Text style={[type.h1, { color: colors.textPrimary }]}>Montar dieta</Text>
      <Text style={[type.body, { color: colors.textSecondary, marginTop: 4 }]}>
        Um cardápio de um dia inteiro, com alimentos reais, batendo sua meta de calorias e macros — pela IA
        (Pro) ou escolhendo uma dieta pronta.
      </Text>

      {/* Meta diária */}
      <Card style={{ marginTop: spacing.lg }}>
        {ctx == null ? (
          <ActivityIndicator color={colors.primary} />
        ) : noGoal ? (
          <View>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", marginBottom: 4 }]}>
              Falta definir sua meta
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Defina sua meta de calorias/macros (ou complete o perfil com peso e objetivo) para montar sua dieta.
            </Text>
            <Button title="Definir minha meta" onPress={() => navigation.navigate("GoalSettings")} />
          </View>
        ) : (
          <View>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
              Sua meta diária {ctx.has_goal_defined ? "" : "(estimada do seu perfil)"}
            </Text>
            <View style={{ flexDirection: "row" }}>
              <MacroPill label="kcal" value={ctx.target_kcal} unit="" color={colors.textPrimary} />
              <MacroPill label="P " value={ctx.target_protein_g} unit="g" color={colors.moduleTraining} />
              <MacroPill label="C " value={ctx.target_carbs_g} unit="g" color={colors.secondary} />
              <MacroPill label="G " value={ctx.target_fat_g} unit="g" color={colors.warning} />
            </View>
          </View>
        )}
      </Card>

      {!noGoal ? (
        <>
          {/* Gerar dieta personalizada com IA (Pro) */}
          <TouchableOpacity activeOpacity={0.85} onPress={handlePersonalized} style={{ marginTop: spacing.lg }}>
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                backgroundColor: colors.primary,
                borderRadius: radius.card,
                padding: spacing.md,
              }}
            >
              <View
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 15,
                  backgroundColor: "rgba(255,255,255,0.22)",
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.md,
                }}
              >
                <Ionicons name="sparkles" size={24} color="#FFFFFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: "#FFFFFF", fontSize: 16 }]}>Gerar minha dieta personalizada</Text>
                <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={2}>
                  A IA pergunta restrições, refeições e o que você gosta e monta{isPro ? "" : " · Pro"}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
            </View>
          </TouchableOpacity>

          {/* Dietas prontas (grátis) */}
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={() => navigation.navigate("DietTemplates")}
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.card,
              padding: spacing.md,
              marginTop: spacing.md,
            }}
          >
            <Ionicons name="restaurant-outline" size={22} color={colors.secondary} />
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
                Quer uma dieta pronta?
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                Clássica, low carb, alta proteína… já ajustadas pra sua meta
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        </>
      ) : null}
    </ScrollView>
  );
}
