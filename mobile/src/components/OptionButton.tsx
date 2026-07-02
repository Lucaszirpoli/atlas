import React from "react";
import { Pressable, Text } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

export function OptionButton({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  const { colors, type, radius, spacing } = useTheme();

  return (
    <Pressable
      onPress={onPress}
      style={{
        borderWidth: 1,
        borderColor: selected ? colors.primary : colors.border,
        backgroundColor: selected ? colors.primaryLight + "22" : colors.surface,
        borderRadius: radius.button,
        paddingVertical: spacing.sm + 2,
        paddingHorizontal: spacing.md,
        marginBottom: spacing.sm,
      }}
    >
      <Text
        style={[
          type.body,
          { color: selected ? colors.primary : colors.textPrimary, fontWeight: selected ? "600" : "400" },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}
