import React from "react";
import { View, type ViewProps } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

type CardProps = ViewProps & {
  padded?: boolean;
  accent?: string;
};

/** Card padrão do app — superfície, cantos arredondados e uma faixa de cor
 * opcional à esquerda (accent).
 *
 * A separação do fundo é feita de dois jeitos, um por tema, porque nenhum dos
 * dois funciona sozinho nos dois: no CLARO a borda fina desenha o card (é o que
 * as referências claras fazem — contorno, não sombra pesada); no ESCURO a borda
 * quase some e quem separa é a superfície ser um degrau mais clara que o fundo,
 * com um halo azul de leve. Card sem nenhum dos dois é o que faz uma tela
 * "parecer HTML". */
export function Card({ padded = true, accent, style, children, ...rest }: CardProps) {
  const { colors, radius, spacing, shadow } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          padding: padded ? spacing.lg : 0,
          borderWidth: 1,
          borderColor: colors.border,
          overflow: "hidden",
        },
        // `shadow` já vem do tema ativo (sombra no claro, halo azul no escuro).
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
