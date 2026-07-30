import React from "react";
import { Image, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

// Cores de avatar da família da marca (azul -> turquesa -> verde -> índigo), pra
// a lista de amigos não destoar do resto do app. Todas escuras o bastante pra
// iniciais brancas ficarem legíveis por cima.
const PALETTE = ["#3563FF", "#0E9F8C", "#234E70", "#6366F1", "#1E9E52", "#4C6EF5"];

/** Avatar circular: foto (só a do PRÓPRIO usuário, salva no aparelho) quando
 * tem, senão as iniciais do nome com cor estável derivada do handle. */
export function Avatar({
  name,
  handle,
  size = 40,
  photoUri,
}: {
  name: string;
  handle: string;
  size?: number;
  photoUri?: string | null;
}) {
  const { colors, type } = useTheme();
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  const color = PALETTE[[...handle].reduce((a, c) => a + c.charCodeAt(0), 0) % PALETTE.length];

  if (photoUri) {
    return (
      <Image
        source={{ uri: photoUri }}
        style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color }}
      />
    );
  }

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
