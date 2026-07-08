import React from "react";
import { Modal, Pressable, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Aviso informativo de botão único (erro, limite atingido, sucesso...) via
 * Modal do RN — Alert.alert é um no-op silencioso no React Native Web. */
export function InfoDialog({
  visible,
  onClose,
  title,
  message,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  message?: string;
}) {
  const { colors, type, spacing, radius, shadow } = useTheme();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.45)", alignItems: "center", justifyContent: "center", padding: spacing.lg }}
      >
        <Pressable
          onPress={() => {}}
          style={[
            { backgroundColor: colors.surface, borderRadius: radius.modal, padding: spacing.lg, width: "100%", maxWidth: 380 },
            shadow.md,
          ]}
        >
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: message ? spacing.xs : spacing.md }]}>{title}</Text>
          {message ? (
            <Text style={[type.body, { color: colors.textSecondary, lineHeight: 22, marginBottom: spacing.md }]}>{message}</Text>
          ) : null}
          <Pressable
            onPress={onClose}
            style={{
              alignSelf: "flex-end",
              paddingVertical: spacing.sm,
              paddingHorizontal: spacing.lg,
              borderRadius: radius.pill,
              backgroundColor: colors.primarySoft,
            }}
          >
            <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]}>Entendi</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
