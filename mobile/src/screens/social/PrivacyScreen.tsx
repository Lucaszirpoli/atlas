import React, { useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { listBlockedUsers, unblockUser } from "../../api/blocksAndReports";
import { getPrivacySettings, updatePrivacySettings, type PrivacySettings } from "../../api/privacy";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";
import type { UserSummary } from "../../api/friends";

export function PrivacyScreen() {
  const { colors, type, spacing } = useTheme();
  const [settings, setSettings] = useState<PrivacySettings | null>(null);
  const [blocked, setBlocked] = useState<UserSummary[]>([]);

  useEffect(() => {
    getPrivacySettings().then(setSettings);
    listBlockedUsers().then(setBlocked);
  }, []);

  async function toggle(patch: Partial<PrivacySettings>) {
    const updated = await updatePrivacySettings(patch);
    setSettings(updated);
  }

  if (!settings) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>Privacidade</Text>

      <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        Visibilidade do perfil
      </Text>
      <OptionButton
        label="Privado (só amigos veem)"
        selected={settings.profile_visibility === "private"}
        onPress={() => toggle({ profile_visibility: "private" })}
      />
      <OptionButton
        label="Público"
        selected={settings.profile_visibility === "public"}
        onPress={() => toggle({ profile_visibility: "public" })}
      />

      <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
        O que compartilhar no feed
      </Text>
      <OptionButton
        label={`Treinos concluídos ${settings.share_workouts ? "✓" : ""}`}
        selected={settings.share_workouts}
        onPress={() => toggle({ share_workouts: !settings.share_workouts })}
      />
      <OptionButton
        label={`Refeições (por post) ${settings.share_meals ? "✓" : ""}`}
        selected={settings.share_meals}
        onPress={() => toggle({ share_meals: !settings.share_meals })}
      />
      <OptionButton
        label={`Fotos de progresso ${settings.share_progress_photos ? "✓" : ""}`}
        selected={settings.share_progress_photos}
        onPress={() => toggle({ share_progress_photos: !settings.share_progress_photos })}
      />

      <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
        Usuários bloqueados
      </Text>
      {blocked.length === 0 ? (
        <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Nenhum usuário bloqueado.</Text>
      ) : (
        blocked.map((u) => (
          <View key={u.id} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.xs }}>
            <Text style={[type.body, { color: colors.textPrimary }]}>@{u.handle}</Text>
            <Text
              style={[type.bodySmall, { color: colors.primary }]}
              onPress={async () => {
                await unblockUser(u.id);
                setBlocked((prev) => prev.filter((b) => b.id !== u.id));
              }}
            >
              Desbloquear
            </Text>
          </View>
        ))
      )}
    </ScrollView>
  );
}
