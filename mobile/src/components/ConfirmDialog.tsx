import React from "react";
import { Modal, Pressable, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Confirmação (ex: "Excluir rotina?") via Modal do RN — Alert.alert é um
 * no-op silencioso no React Native Web (não aparece nada, nada executa),
 * então qualquer confirmação destrutiva precisa passar por aqui, não por
 * Alert.alert, pra funcionar também no navegador. */
export function ConfirmDialog({
  visible,
  onClose,
  title,
  message,
  confirmLabel = "Confirmar",
  destructive = false,
  onConfirm,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  message?: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
}) {
  const { colors, type, spacing, radius, shadow } = useTheme();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{
          flex: 1,
          backgroundColor: "rgba(0,0,0,0.45)",
          alignItems: "center",
          justifyContent: "center",
          padding: spacing.lg,
        }}
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
          <View style={{ flexDirection: "row", gap: spacing.sm, justifyContent: "flex-end" }}>
            <Pressable
              onPress={onClose}
              style={{ paddingVertical: spacing.sm, paddingHorizontal: spacing.md, borderRadius: radius.pill }}
            >
              <Text style={[type.body, { color: colors.textSecondary, fontWeight: "700" }]}>Cancelar</Text>
            </Pressable>
            <Pressable
              onPress={() => {
                onClose();
                onConfirm();
              }}
              style={{
                paddingVertical: spacing.sm,
                paddingHorizontal: spacing.md,
                borderRadius: radius.pill,
                backgroundColor: destructive ? colors.danger : colors.primary,
              }}
            >
              <Text style={[type.body, { color: "#FFFFFF", fontWeight: "700" }]}>{confirmLabel}</Text>
            </Pressable>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
