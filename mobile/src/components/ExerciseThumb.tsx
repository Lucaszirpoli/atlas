import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { Image, Modal, Pressable, Text, useWindowDimensions, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Miniatura da foto do exercício (tipo ícone) ao lado do nome. Toque abre a
 * foto ampliada num modal (lightbox), toque no fundo fecha. Sem imagem,
 * mostra um placeholder discreto. */
export function ExerciseThumb({
  url,
  name,
  size = 44,
}: {
  url?: string | null;
  name?: string;
  size?: number;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const win = useWindowDimensions();
  const [open, setOpen] = useState(false);
  // win.width pode vir 0 dentro do Modal no RN Web — garante um tamanho sensato.
  const bigSize = win.width > 0 ? Math.min(win.width - 32, 400) : 320;

  if (!url) {
    return (
      <View
        style={{
          width: size,
          height: size,
          borderRadius: 12,
          backgroundColor: colors.surfaceAlt,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Ionicons name="barbell-outline" size={size * 0.5} color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <>
      <Pressable onPress={() => setOpen(true)} hitSlop={6}>
        <Image
          source={{ uri: url }}
          resizeMode="cover"
          style={{ width: size, height: size, borderRadius: 12, backgroundColor: colors.surfaceAlt }}
        />
        {/* dica sutil de que dá pra ampliar */}
        <View
          style={{
            position: "absolute",
            right: -3,
            bottom: -3,
            backgroundColor: colors.textPrimary,
            borderRadius: 8,
            width: 16,
            height: 16,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="expand" size={10} color={colors.bg} />
        </View>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable
          onPress={() => setOpen(false)}
          style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.85)", alignItems: "center", justifyContent: "center", padding: spacing.lg }}
        >
          {name ? (
            <Text style={[type.h2, { color: "#FFFFFF", marginBottom: spacing.md, textAlign: "center" }]}>{name}</Text>
          ) : null}
          <Image
            source={{ uri: url }}
            resizeMode="contain"
            style={{ width: bigSize, height: bigSize, borderRadius: radius.card, backgroundColor: "rgba(255,255,255,0.06)" }}
          />
          <Text style={[type.caption, { color: "rgba(255,255,255,0.7)", marginTop: spacing.md }]}>
            Toque para fechar
          </Text>
        </Pressable>
      </Modal>
    </>
  );
}
