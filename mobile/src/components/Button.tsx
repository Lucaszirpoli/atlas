import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type PressableProps,
} from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type ButtonProps = PressableProps & {
  title: string;
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
  icon?: string;
  /** Para botão em espaço apertado (dois lado a lado dentro de um card do
   * chat). Reduz o respiro lateral, que é fixo e não encolhe sozinho. */
  compact?: boolean;
};

export function Button({
  title,
  variant = "primary",
  loading,
  disabled,
  icon,
  compact,
  style,
  ...rest
}: ButtonProps) {
  const { colors, type, radius, spacing, shadow } = useTheme();

  const backgroundColor =
    variant === "primary"
      ? colors.primary
      : variant === "secondary"
        ? colors.secondary
        : "transparent";
  const textColor = variant === "ghost" ? colors.primary : colors.textOnPrimary;
  const isSolid = variant !== "ghost";

  return (
    <Pressable
      disabled={disabled || loading}
      style={(state) => [
        styles.base,
        {
          backgroundColor,
          borderRadius: radius.pill,
          paddingVertical: spacing.md - 1,
          paddingHorizontal: compact ? spacing.sm : spacing.lg,
          transform: [{ scale: state.pressed ? 0.98 : 1 }],
          opacity: disabled ? 0.45 : 1,
        },
        isSolid && !disabled ? shadow.sm : null,
        typeof style === "function" ? style(state) : style,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator color={textColor} />
      ) : (
        <View style={styles.row}>
          {icon ? <Text style={[styles.icon, { color: textColor }]}>{icon}</Text> : null}
          {/* numberOfLines=1 evita o rótulo quebrar em duas linhas
              ("Desca/rtar"), mas sozinho ele TRUNCA quando falta largura — era
              o bug do "Con..." ("Confirmar" e "Concluir" viravam os dois a
              mesma coisa) nos botões dentro do card do chat. adjustsFontSizeToFit
              faz o texto DIMINUIR até caber, em vez de cortar; segura também
              quem usa fonte grande do sistema. */}
          <Text
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.75}
            style={[type.body, styles.text, { color: textColor }]}
          >
            {title}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  icon: {
    fontSize: 16,
  },
  text: {
    fontWeight: "700",
    fontSize: 16,
    letterSpacing: 0.2,
  },
});
