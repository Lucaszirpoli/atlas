import React from "react";
import { ScrollView, Text, View } from "react-native";

import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

export function HomeScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const { user } = useAuth();

  return (
    <ScrollView
      contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}
    >
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
        Olá, {user?.display_name?.split(" ")[0] ?? "tudo bem"}
      </Text>
      <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
        Seu resumo do dia vai aparecer aqui a partir da Fase 1 (nutrição) e Fase 2 (treino).
      </Text>

      <View
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          borderWidth: 1,
          borderColor: colors.border,
          padding: spacing.md,
        }}
      >
        <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
          Plano atual
        </Text>
        <Text style={[type.body, { color: colors.textSecondary }]}>
          {user?.plan === "pro" ? "Pro" : "Free"}
        </Text>
      </View>
    </ScrollView>
  );
}
