import React from "react";
import { Text, View } from "react-native";

import { useTheme } from "../../theme/ThemeProvider";

export function PlaceholderScreen({ title, subtitle }: { title: string; subtitle: string }) {
  const { colors, type, spacing } = useTheme();

  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        padding: spacing.lg,
        backgroundColor: colors.bg,
      }}
    >
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        {title}
      </Text>
      <Text style={[type.body, { color: colors.textSecondary, textAlign: "center" }]}>
        {subtitle}
      </Text>
    </View>
  );
}
