import React from "react";
import { Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { fontFamily } from "../theme/typography";
import { useTheme } from "../theme/ThemeProvider";

export function ProgressRing({
  progress,
  size = 140,
  strokeWidth = 14,
  label,
  value,
  color,
  valueSize,
}: {
  progress: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  value: string;
  color?: string;
  /** Sobrescreve o tamanho da fonte do número central (senão escala com o anel). */
  valueSize?: number;
}) {
  const { colors, type } = useTheme();
  const ringColor = color ?? colors.primary;

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(progress, 0), 1);
  const strokeDashoffset = circumference * (1 - clamped);

  // Escala a tipografia com o tamanho do anel para nunca vazar/tapar o gráfico.
  const numberSize = valueSize ?? Math.max(16, Math.round(size * 0.26));
  const labelSize = Math.max(10, Math.round(size * 0.1));

  return (
    // Largura travada em `size`: sem isso, se o texto abaixo (ex: "/ 3385
    // kcal") for mais largo que o anel, o container cresce e rouba espaço
    // de quem estiver ao lado (ex: as barras de macro na tela de Dieta),
    // que por padrão não encolhem no RN — e o texto vaza pra fora da tela.
    <View style={{ width: size, alignItems: "center" }}>
      <Svg width={size} height={size} style={{ transform: [{ rotate: "-90deg" }] }}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={colors.border}
          strokeWidth={strokeWidth}
          fill="none"
        />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={ringColor}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
        />
      </Svg>
      {/* Texto embaixo do anel, fora da sobreposição — sem tampação. */}
      <View style={{ marginTop: 8, alignItems: "center", width: size }}>
        <Text
          style={{
            color: colors.textPrimary,
            fontFamily: fontFamily.display,
            fontSize: numberSize,
            lineHeight: numberSize + 2,
          }}
          numberOfLines={1}
        >
          {value}
        </Text>
        {label ? (
          <Text
            style={[type.caption, { color: colors.textSecondary, fontSize: labelSize, textAlign: "center", marginTop: 1 }]}
            numberOfLines={1}
          >
            {label}
          </Text>
        ) : null}
      </View>
    </View>
  );
}
