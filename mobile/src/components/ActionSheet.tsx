import React from "react";
import { Modal, Pressable, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

export type ActionSheetOption = {
  label: string;
  onPress: () => void;
  destructive?: boolean;
};

/** Menu de ações (editar/duplicar/excluir...) via Modal do RN — funciona em
 * iOS, Android E web, diferente de Alert.alert com múltiplos botões (que é
 * um no-op silencioso no React Native Web: nada aparece nem executa). */
export function ActionSheet({
  visible,
  onClose,
  title,
  options,
}: {
  visible: boolean;
  onClose: () => void;
  title?: string;
  options: ActionSheetOption[];
}) {
  const { colors, type, spacing, radius, shadow } = useTheme();

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{
          flex: 1,
          backgroundColor: "rgba(0,0,0,0.45)",
          justifyContent: "flex-end",
        }}
      >
        <Pressable
          onPress={() => {}}
          style={[
            {
              backgroundColor: colors.surface,
              borderTopLeftRadius: radius.modal,
              borderTopRightRadius: radius.modal,
              padding: spacing.lg,
              paddingBottom: spacing.xl,
            },
            shadow.md,
          ]}
        >
          {title ? (
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md, fontSize: 17 }]} numberOfLines={1}>
              {title}
            </Text>
          ) : null}
          {options.map((opt, i) => (
            <Pressable
              key={i}
              onPress={() => {
                onClose();
                opt.onPress();
              }}
              style={({ pressed }) => ({
                paddingVertical: spacing.md,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.border,
                opacity: pressed ? 0.6 : 1,
              })}
            >
              <Text
                style={[
                  type.body,
                  { color: opt.destructive ? colors.danger : colors.textPrimary, fontWeight: "600" },
                ]}
              >
                {opt.label}
              </Text>
            </Pressable>
          ))}
          <Pressable
            onPress={onClose}
            style={{
              marginTop: spacing.sm,
              paddingVertical: spacing.md,
              alignItems: "center",
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
            }}
          >
            <Text style={[type.body, { color: colors.textSecondary, fontWeight: "700" }]}>Cancelar</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
