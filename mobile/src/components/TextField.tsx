import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { StyleSheet, Text, TextInput, TouchableOpacity, View, type TextInputProps } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type TextFieldProps = TextInputProps & {
  label: string;
  error?: string;
};

export function TextField({ label, error, style, onFocus, onBlur, secureTextEntry, ...rest }: TextFieldProps) {
  const { colors, type, radius, spacing } = useTheme();
  const [focused, setFocused] = useState(false);
  const [revealPassword, setRevealPassword] = useState(false);

  const borderColor = error ? colors.danger : focused ? colors.primary : "transparent";

  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs, marginLeft: spacing.xs }]}>
        {label}
      </Text>
      <View>
        <TextInput
          placeholderTextColor={colors.textSecondary}
          secureTextEntry={secureTextEntry && !revealPassword}
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
              paddingRight: secureTextEntry ? spacing.xl + spacing.md : spacing.md,
              backgroundColor: colors.surfaceAlt,
            },
            style,
          ]}
          {...rest}
        />
        {secureTextEntry ? (
          <TouchableOpacity
            onPress={() => setRevealPassword((v) => !v)}
            hitSlop={10}
            style={{ position: "absolute", right: spacing.md, top: 0, bottom: 0, justifyContent: "center" }}
          >
            <Ionicons
              name={revealPassword ? "eye-off-outline" : "eye-outline"}
              size={20}
              color={colors.textSecondary}
            />
          </TouchableOpacity>
        ) : null}
      </View>
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
