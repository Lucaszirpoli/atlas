import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";
import { DEFAULT_HOME_ORDER, HOME_BLOCK_META, useHomeLayout } from "../../utils/homeLayout";

/** Configurações > Layout da tela inicial. A pessoa reordena os blocos do
 * Coaching (a home) com setas pra cima/baixo. O cabeçalho (saudação/avatar/
 * Desafios) fica sempre fixo — só o conteúdo abaixo dele é reordenável. */
export function HomeLayoutScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const { order, move, resetToDefault } = useHomeLayout();

  const isDefault = order.length === DEFAULT_HOME_ORDER.length && order.every((id, i) => id === DEFAULT_HOME_ORDER[i]);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 18 }]}>
        Escolha a ordem dos blocos da sua tela inicial. O cabeçalho (saudação, Desafios e Amigos e feed) fica sempre
        no topo.
      </Text>

      <Card padded={false} style={{ marginBottom: spacing.lg }}>
        {order.map((id, index) => {
          const meta = HOME_BLOCK_META[id];
          return (
            <View
              key={id}
              style={{
                flexDirection: "row",
                alignItems: "center",
                padding: spacing.md,
                borderTopWidth: index === 0 ? 0 : 1,
                borderTopColor: colors.border,
              }}
            >
              <View
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 12,
                  backgroundColor: colors.primary + "18",
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.md,
                }}
              >
                <Ionicons name={meta.icon as keyof typeof Ionicons.glyphMap} size={19} color={colors.primary} />
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]} numberOfLines={1}>
                  {meta.label}
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]} numberOfLines={1}>
                  {meta.description}
                </Text>
              </View>
              <View style={{ flexDirection: "row", gap: 6 }}>
                <ArrowButton
                  icon="chevron-up"
                  disabled={index === 0}
                  onPress={() => move(id, -1)}
                />
                <ArrowButton
                  icon="chevron-down"
                  disabled={index === order.length - 1}
                  onPress={() => move(id, 1)}
                />
              </View>
            </View>
          );
        })}
      </Card>

      <TouchableOpacity
        onPress={resetToDefault}
        disabled={isDefault}
        activeOpacity={0.7}
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          paddingVertical: spacing.md,
          borderRadius: radius.button,
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          opacity: isDefault ? 0.5 : 1,
        }}
      >
        <Ionicons name="refresh" size={17} color={colors.textPrimary} />
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
          {isDefault ? "Essa já é a ordem padrão" : "Restaurar ordem padrão"}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function ArrowButton({
  icon,
  disabled,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  disabled?: boolean;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      hitSlop={8}
      style={{
        width: 34,
        height: 34,
        borderRadius: 10,
        backgroundColor: colors.surfaceAlt,
        alignItems: "center",
        justifyContent: "center",
        opacity: disabled ? 0.35 : 1,
      }}
    >
      <Ionicons name={icon} size={18} color={colors.textPrimary} />
    </TouchableOpacity>
  );
}
