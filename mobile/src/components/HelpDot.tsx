import React, { useState } from "react";
import { Modal, Pressable, Text, TouchableOpacity, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Pontinho de interrogação que abre uma explicação curta ao toque.
 * Usa Modal do RN (funciona em iOS, Android e web, diferente do Alert). */
export function HelpDot({ title, text }: { title: string; text: string }) {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const [open, setOpen] = useState(false);

  return (
    <>
      <TouchableOpacity
        onPress={() => setOpen(true)}
        hitSlop={10}
        accessibilityLabel={`O que é ${title}?`}
        style={{
          width: 18,
          height: 18,
          borderRadius: 9,
          backgroundColor: colors.surfaceAlt,
          borderWidth: 1,
          borderColor: colors.border,
          alignItems: "center",
          justifyContent: "center",
          marginLeft: 6,
        }}
      >
        <Text style={{ color: colors.textSecondary, fontSize: 11, fontWeight: "800" }}>?</Text>
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable
          onPress={() => setOpen(false)}
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
              {
                backgroundColor: colors.surface,
                borderRadius: radius.modal,
                padding: spacing.lg,
                width: "100%",
                maxWidth: 380,
              },
              shadow.md,
            ]}
          >
            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
              <View
                style={{
                  width: 30,
                  height: 30,
                  borderRadius: 10,
                  backgroundColor: colors.primarySoft,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.sm,
                }}
              >
                <Text style={{ color: colors.primary, fontWeight: "800" }}>?</Text>
              </View>
              <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{title}</Text>
            </View>
            <Text style={[type.body, { color: colors.textSecondary, lineHeight: 22 }]}>{text}</Text>
            <TouchableOpacity
              onPress={() => setOpen(false)}
              style={{
                alignSelf: "flex-end",
                marginTop: spacing.md,
                paddingVertical: spacing.sm,
                paddingHorizontal: spacing.lg,
                borderRadius: radius.pill,
                backgroundColor: colors.primarySoft,
              }}
            >
              <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]}>Entendi</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}
