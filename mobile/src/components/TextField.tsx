import React from "react";
import { StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type TextFieldProps = TextInputProps & {
  label: string;
  error?: string;
};

export function TextField({ label, error, style, ...rest }: TextFieldProps) {
  const { colors, type, radius, spacing } = useTheme();

  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
        {label}
      </Text>
      <TextInput
        placeholderTextColor={colors.textSecondary}
        style={[
          type.body,
          styles.input,
          {
            color: colors.textPrimary,
            borderColor: error ? colors.danger : colors.border,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            backgroundColor: colors.surface,
          },
          style,
        ]}
        {...rest}
      />
      {error ? (
        <Text style={[type.caption, { color: colors.danger, marginTop: spacing.xs }]}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    height: 48,
    borderWidth: 1,
  },
});
