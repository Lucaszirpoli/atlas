import React, { useState } from "react";
import { StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type TextFieldProps = TextInputProps & {
  label: string;
  error?: string;
};

export function TextField({ label, error, style, onFocus, onBlur, ...rest }: TextFieldProps) {
  const { colors, type, radius, spacing } = useTheme();
  const [focused, setFocused] = useState(false);

  const borderColor = error ? colors.danger : focused ? colors.primary : "transparent";

  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs, marginLeft: spacing.xs }]}>
        {label}
      </Text>
      <TextInput
        placeholderTextColor={colors.textSecondary}
        onFocus={(e) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          onBlur?.(e);
        }}
        style={[
          type.body,
          styles.input,
          {
            color: colors.textPrimary,
            borderColor,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            backgroundColor: colors.surfaceAlt,
          },
          style,
        ]}
        {...rest}
      />
      {error ? (
        <Text style={[type.caption, { color: colors.danger, marginTop: spacing.xs, marginLeft: spacing.xs }]}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  input: {
    height: 54,
    borderWidth: 2,
  },
});
