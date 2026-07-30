import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Caixa de seleção com rótulo — a linha inteira é a área de toque, não só o
 * quadradinho de 22px (que é alvo pequeno demais pra dedo). */
export function Checkbox({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <Pressable
      onPress={() => onChange(!checked)}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={label}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        gap: spacing.sm,
        paddingVertical: spacing.sm,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 6,
          borderWidth: checked ? 0 : 1.5,
          borderColor: colors.border,
          backgroundColor: checked ? colors.primary : "transparent",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {checked ? <Ionicons name="checkmark" size={15} color={colors.textOnPrimary} /> : null}
      </View>
      <Text style={[type.bodySmall, { color: colors.textSecondary, flex: 1 }]}>{label}</Text>
    </Pressable>
  );
}
