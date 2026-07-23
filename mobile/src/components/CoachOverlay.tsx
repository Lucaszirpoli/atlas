import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Text, TouchableOpacity, View } from "react-native";

import type { WorkoutOverlay } from "../api/coaching";
import { useTheme } from "../theme/ThemeProvider";

const ICON: Record<string, keyof typeof Ionicons.glyphMap> = {
  technique: "flash",
  progression: "trending-up",
  exercise_swap: "swap-horizontal",
  deload: "bed",
};

/** Bloco de overlay do coach num exercício (técnica / subir carga / troca).
 * `onRemove` opcional: na prévia dá pra remover (desfazer); na execução é só
 * leitura. O chamador decide qual endpoint desfaz (source technique vs action). */
export function CoachOverlayBlock({
  overlay,
  onRemove,
}: {
  overlay: WorkoutOverlay;
  onRemove?: (o: WorkoutOverlay) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const destaque =
    overlay.kind === "progression" && overlay.payload?.new_weight
      ? `${overlay.payload.new_weight} kg`
      : overlay.kind === "exercise_swap" && overlay.payload?.to_name
      ? overlay.payload.to_name
      : null;
  return (
    <View
      style={{
        marginTop: spacing.sm,
        backgroundColor: colors.surfaceAlt,
        borderRadius: radius.card,
        borderLeftWidth: 3,
        borderLeftColor: colors.primary,
        padding: spacing.sm,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 3 }}>
        <Ionicons name={ICON[overlay.kind] ?? "sparkles"} size={14} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "700", flex: 1 }]} numberOfLines={1}>
          Coach · {overlay.title}
        </Text>
        {onRemove ? (
          <TouchableOpacity onPress={() => onRemove(overlay)} hitSlop={8}>
            <Text style={[type.caption, { color: colors.textSecondary }]}>Remover</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      {destaque ? (
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800", marginBottom: 2 }]}>
          → {destaque}
        </Text>
      ) : null}
      <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 18 }]}>{overlay.detail}</Text>
    </View>
  );
}

/** Banner global de deload — fica no topo do treino (não é por exercício). */
export function DeloadBanner({
  overlay,
  onRemove,
}: {
  overlay: WorkoutOverlay;
  onRemove?: (o: WorkoutOverlay) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View
      style={{
        marginBottom: spacing.md,
        backgroundColor: colors.warning + "18",
        borderRadius: radius.card,
        borderWidth: 1,
        borderColor: colors.warning + "44",
        padding: spacing.md,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 3 }}>
        <Ionicons name="bed" size={16} color={colors.warning} />
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800", flex: 1 }]}>{overlay.title}</Text>
        {onRemove ? (
          <TouchableOpacity onPress={() => onRemove(overlay)} hitSlop={8}>
            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "600" }]}>Encerrar</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 18 }]}>{overlay.detail}</Text>
    </View>
  );
}
