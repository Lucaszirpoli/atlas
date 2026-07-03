import React from "react";
import { View, type ViewProps } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type CardProps = ViewProps & {
  padded?: boolean;
  accent?: string;
};

/** Card elevado padrão do app — superfície clara, cantos arredondados,
 * sombra suave e uma faixa de cor opcional à esquerda (accent). */
export function Card({ padded = true, accent, style, children, ...rest }: CardProps) {
  const { colors, radius, spacing, shadow } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          padding: padded ? spacing.lg : 0,
          overflow: "hidden",
        },
        shadow.sm,
        style,
      ]}
      {...rest}
    >
      {accent ? (
        <View
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: 5,
            backgroundColor: accent,
          }}
        />
      ) : null}
      {children}
    </View>
  );
}
