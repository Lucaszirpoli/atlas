import React from "react";
import Svg, { Path } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";

/** O SLOGAN do ATLAS. Mora junto da logo porque é parte da marca, não texto de
 * tela — quem mostrar os dois juntos (abertura, login) usa esta constante em vez
 * de digitar a frase de novo e ela virar duas versões diferentes. */
export const ATLAS_SLOGAN = "O treino perfeito não depende da sorte. Depende da ciência.";

/** Logo do ATLAS — um monólito/pilar isométrico. É desenhado como uma silhueta
 * cheia (`color`) com uma costura em Y (`seam`, na cor do fundo) por cima, que
 * "corta" o vinco central e as duas diagonais até a base — igual à marca.
 *
 * A FORMA é a mesma de sempre; o que mudou com a identidade nova é a cor: o
 * padrão passou a ser o azul de marca em vez do texto, que era o que fazia a
 * logo aparecer preta no claro e branca no escuro, sem cor nenhuma.
 *
 * `seam` deve ser a cor da superfície onde a logo está (por padrão o fundo do
 * tema), pra costura parecer um recorte de verdade. */
export function AtlasLogo({
  size = 96,
  color,
  seam,
}: {
  size?: number;
  color?: string;
  seam?: string;
}) {
  const { colors } = useTheme();
  const fill = color ?? colors.primary;
  const seamColor = seam ?? colors.bg;
  // proporção alta (2:3) do viewBox
  const w = size;
  const h = size * (300 / 200);

  // silhueta externa (hexágono do pilar) + a costura em Y por cima
  const SILHOUETTE = "M100 16 L28 60 L32 236 L100 284 L168 236 L172 60 Z";
  const SEAM = "M100 22 L100 210 M100 210 L40 232 M100 210 L160 232";
  const seamWidth = size * 0.038;

  return (
    <Svg width={w} height={h} viewBox="0 0 200 300">
      <Path d={SILHOUETTE} fill={fill} />
      <Path
        d={SEAM}
        stroke={seamColor}
        strokeWidth={seamWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </Svg>
  );
}
