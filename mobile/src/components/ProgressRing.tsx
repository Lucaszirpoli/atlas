import React from "react";
import { Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";

export function ProgressRing({
  progress,
  size = 140,
  strokeWidth = 14,
  label,
  value,
  color,
}: {
  progress: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  value: string;
  color?: string;
}) {
  const { colors, type } = useTheme();
  const ringColor = color ?? colors.primary;

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(Math.max(progress, 0), 1);
  const strokeDashoffset = circumference * (1 - clamped);

  return (
    <View style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size}>
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
          rotation={-90}
          origin={`${size / 2}, ${size / 2}`}
        />
      </Svg>
      <View style={{ position: "absolute", alignItems: "center" }}>
        <Text style={[type.h1, { color: colors.textPrimary }]}>{value}</Text>
        <Text style={[type.caption, { color: colors.textSecondary }]}>{label}</Text>
      </View>
    </View>
  );
}
