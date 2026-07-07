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
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      {/* Rotaciona o SVG inteiro -90° para o anel começar no topo — evita as
          props rotation/origin do react-native-svg, que geram atributos DOM
          inválidos na web. */}
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
      {/* Overlay ancorado no centro do anel (preenche a box e centraliza) — sem
          isso o texto escorrega pro canto e tapa o gráfico em anéis pequenos. */}
      <View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          alignItems: "center",
          justifyContent: "center",
          paddingHorizontal: strokeWidth,
        }}
        pointerEvents="none"
      >
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
