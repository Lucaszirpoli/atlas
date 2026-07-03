import React from "react";
import { Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

const PALETTE = ["#1F7A5C", "#FF6B35", "#4A5B8C", "#E8637A", "#3B82C4", "#E8A33D"];

/** Avatar circular com as iniciais do nome, cor estável derivada do handle. */
export function Avatar({ name, handle, size = 40 }: { name: string; handle: string; size?: number }) {
  const { colors, type } = useTheme();
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  const color = PALETTE[[...handle].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];

  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: color,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={[type.bodySmall, { color: colors.textOnPrimary, fontWeight: "800", fontSize: size * 0.38 }]}>
        {initials || "?"}
      </Text>
    </View>
  );
}
