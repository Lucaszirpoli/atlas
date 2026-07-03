import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { ScrollView, Switch, Text, TouchableOpacity, View } from "react-native";

import { listBlockedUsers, unblockUser } from "../../api/blocksAndReports";
import { getPrivacySettings, updatePrivacySettings, type PrivacySettings } from "../../api/privacy";
import type { UserSummary } from "../../api/friends";
import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

export function PrivacyScreen() {
  const { colors, type, spacing } = useTheme();
  const [settings, setSettings] = useState<PrivacySettings | null>(null);
  const [blocked, setBlocked] = useState<UserSummary[]>([]);

  useEffect(() => {
    getPrivacySettings().then(setSettings);
    listBlockedUsers().then(setBlocked);
  }, []);

  async function toggle(patch: Partial<PrivacySettings>) {
    setSettings(await updatePrivacySettings(patch));
  }

  if (!settings) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Visibilidade do perfil
      </Text>
      <Card style={{ marginBottom: spacing.lg }}>
        <OptionButton
          label="Privado — só amigos veem seu perfil"
          selected={settings.profile_visibility === "private"}
          onPress={() => toggle({ profile_visibility: "private" })}
        />
        <OptionButton
          label="Público — qualquer pessoa pode ver"
          selected={settings.profile_visibility === "public"}
          onPress={() => toggle({ profile_visibility: "public" })}
        />
      </Card>

      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        O que vai para o feed
      </Text>
      <Card padded={false} style={{ marginBottom: spacing.lg }}>
        <ToggleRow
          icon="barbell"
          iconColor={colors.moduleTraining}
          label="Treinos concluídos"
          hint="Postados automaticamente ao finalizar"
          value={settings.share_workouts}
          onChange={(v) => toggle({ share_workouts: v })}
          first
        />
        <ToggleRow
          icon="restaurant"
          iconColor={colors.moduleNutrition}
          label="Refeições"
          hint="Você escolhe compartilhar uma a uma"
          value={settings.share_meals}
          onChange={(v) => toggle({ share_meals: v })}
        />
        <ToggleRow
          icon="camera"
          iconColor={colors.moduleSocial}
          label="Fotos de progresso"
          hint="Sempre opt-in, por foto"
          value={settings.share_progress_photos}
          onChange={(v) => toggle({ share_progress_photos: v })}
        />
      </Card>

      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Usuários bloqueados
      </Text>
      <Card padded={false}>
        {blocked.length === 0 ? (
          <Text style={[type.bodySmall, { color: colors.textSecondary, padding: spacing.md }]}>
            Nenhum usuário bloqueado.
          </Text>
        ) : (
          blocked.map((u, i) => (
            <View
              key={u.id}
              style={{
                flexDirection: "row",
                alignItems: "center",
                padding: spacing.md,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.border,
              }}
            >
              <Avatar name={u.display_name} handle={u.handle} size={36} />
              <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, marginLeft: spacing.sm }]}>
                @{u.handle}
              </Text>
              <TouchableOpacity
                onPress={async () => {
                  await unblockUser(u.id);
                  setBlocked((prev) => prev.filter((b) => b.id !== u.id));
                }}
              >
                <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>Desbloquear</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </Card>
    </ScrollView>
  );
}

function ToggleRow({
  icon,
  iconColor,
  label,
  hint,
  value,
  onChange,
  first,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
  first?: boolean;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        padding: spacing.md,
        borderTopWidth: first ? 0 : 1,
        borderTopColor: colors.border,
      }}
    >
      <View
        style={{
          width: 38,
          height: 38,
          borderRadius: 13,
          backgroundColor: iconColor + "1E",
          alignItems: "center",
          justifyContent: "center",
          marginRight: spacing.sm,
        }}
      >
        <Ionicons name={icon} size={18} color={iconColor} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{label}</Text>
        <Text style={[type.caption, { color: colors.textSecondary }]}>{hint}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: colors.border, true: colors.primaryLight }}
        thumbColor={colors.surface}
      />
    </View>
  );
}
