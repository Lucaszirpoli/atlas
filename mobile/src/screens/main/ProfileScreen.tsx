import React from "react";
import { ScrollView, Text, View } from "react-native";

import { Button } from "../../components/Button";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

export function ProfileScreen() {
  const { colors, type, spacing } = useTheme();
  const { user, signOut } = useAuth();

  return (
    <ScrollView
      contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}
    >
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>
        Perfil
      </Text>

      <View style={{ marginBottom: spacing.lg }}>
        <Text style={[type.body, { color: colors.textPrimary }]}>{user?.display_name}</Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary }]}>@{user?.handle}</Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{user?.email}</Text>
      </View>

      <Button title="Sair" variant="ghost" onPress={signOut} />
    </ScrollView>
  );
}
