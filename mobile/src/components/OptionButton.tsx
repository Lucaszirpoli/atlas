import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Pressable, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

export function OptionButton({
  label,
  selected,
  onPress,
  compact = false,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  compact?: boolean;
}) {
  const { colors, type, radius, spacing } = useTheme();

  if (compact) {
    // Variante "chip" para grupos horizontais (dias, notas 1-5, tipos)
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => ({
          borderRadius: radius.pill,
          paddingVertical: spacing.sm,
          paddingHorizontal: spacing.md,
          backgroundColor: selected ? colors.primary : colors.surface,
          borderWidth: 1.5,
          borderColor: selected ? colors.primary : colors.border,
          transform: [{ scale: pressed ? 0.97 : 1 }],
          marginBottom: spacing.sm,
        })}
      >
        <Text
          style={[
            type.bodySmall,
            {
              color: selected ? colors.textOnPrimary : colors.textPrimary,
              fontWeight: selected ? "700" : "500",
            },
          ]}
        >
          {label}
        </Text>
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        borderWidth: 1.5,
        borderColor: selected ? colors.primary : colors.border,
        backgroundColor: selected ? colors.primarySoft : colors.surface,
        borderRadius: radius.button,
        paddingVertical: spacing.md,
        paddingHorizontal: spacing.md,
        marginBottom: spacing.sm,
        transform: [{ scale: pressed ? 0.98 : 1 }],
      })}
    >
      <View
        style={{
          width: 22,
          height: 22,
          borderRadius: 11,
          borderWidth: 2,
          borderColor: selected ? colors.primary : colors.border,
          backgroundColor: selected ? colors.primary : "transparent",
          alignItems: "center",
          justifyContent: "center",
          marginRight: spacing.md,
        }}
      >
        {selected ? <Ionicons name="checkmark" size={14} color={colors.textOnPrimary} /> : null}
      </View>
      <Text
        style={[
          type.body,
          {
            flex: 1,
            color: selected ? colors.primaryDark : colors.textPrimary,
            fontWeight: selected ? "700" : "400",
          },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}
