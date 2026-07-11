import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { useTheme, type ThemeMode } from "../../theme/ThemeProvider";

export function ProfileScreen() {
  const { colors, type, spacing, mode, setMode } = useTheme();
  const navigation = useNavigation<any>();
  const { user, signOut } = useAuth();

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.xl + spacing.md, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Cabeçalho do perfil */}
      <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
        <Avatar name={user?.display_name ?? "?"} handle={user?.handle ?? "?"} size={86} />
        <Text style={[type.h1, { color: colors.textPrimary, marginTop: spacing.md }]}>
          {user?.display_name}
        </Text>
        <Text style={[type.body, { color: colors.textSecondary }]}>@{user?.handle}</Text>
      </View>

      {/* Plano */}
      <Card
        accent={user?.plan === "pro" ? colors.secondary : colors.primary}
        style={{ marginBottom: spacing.lg }}
      >
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <View
            style={{
              width: 44,
              height: 44,
              borderRadius: 15,
              backgroundColor: user?.plan === "pro" ? colors.secondarySoft : colors.primarySoft,
              alignItems: "center",
              justifyContent: "center",
              marginRight: spacing.md,
            }}
          >
            <Ionicons
              name={user?.plan === "pro" ? "star" : "leaf"}
              size={21}
              color={user?.plan === "pro" ? colors.secondary : colors.primary}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.h2, { color: colors.textPrimary }]}>
              Plano {user?.plan === "pro" ? "Pro" : "Free"}
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {user?.plan === "pro"
                ? "Assistente de IA ilimitado + foto de refeição"
                : "Treino e dieta manual são livres · a IA é do Pro"}
            </Text>
          </View>
          {user?.plan !== "pro" ? (
            <TouchableOpacity
              onPress={() => navigation.navigate("Paywall")}
              style={{
                backgroundColor: colors.primary,
                borderRadius: 999,
                paddingVertical: 8,
                paddingHorizontal: 16,
              }}
            >
              <Text style={[type.caption, { color: colors.textOnPrimary, fontWeight: "800" }]}>Assinar</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </Card>

      {/* Aparência: claro / escuro / acompanhar o sistema */}
      <Card style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="contrast" size={19} color={colors.textSecondary} style={{ marginRight: spacing.sm }} />
          <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>Aparência</Text>
        </View>
        <View
          style={{
            flexDirection: "row",
            backgroundColor: colors.surfaceAlt,
            borderRadius: 999,
            padding: 4,
          }}
        >
          {(
            [
              { key: "system", label: "Sistema", icon: "phone-portrait" },
              { key: "light", label: "Claro", icon: "sunny" },
              { key: "dark", label: "Escuro", icon: "moon" },
            ] as { key: ThemeMode; label: string; icon: keyof typeof Ionicons.glyphMap }[]
          ).map((opt) => {
            const active = mode === opt.key;
            return (
              <TouchableOpacity
                key={opt.key}
                onPress={() => setMode(opt.key)}
                activeOpacity={0.8}
                style={{
                  flex: 1,
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 5,
                  paddingVertical: 9,
                  borderRadius: 999,
                  backgroundColor: active ? colors.surface : "transparent",
                  ...(active ? { shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 4, elevation: 1 } : {}),
                }}
              >
                <Ionicons
                  name={opt.icon}
                  size={15}
                  color={active ? colors.primary : colors.textSecondary}
                />
                <Text
                  style={[
                    type.caption,
                    { color: active ? colors.textPrimary : colors.textSecondary, fontWeight: active ? "700" : "400" },
                  ]}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </Card>

      {/* Menu */}
      <Card padded={false} style={{ marginBottom: spacing.lg }}>
        <MenuRow icon="trending-up" label="Evolução" onPress={() => navigation.navigate("Evolution")} first />
        <MenuRow icon="moon" label="Sono" onPress={() => navigation.navigate("Sleep")} />
        <MenuRow icon="mail" label="E-mail" trailing={user?.email} />
      </Card>

      <TouchableOpacity
        onPress={signOut}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: spacing.md }}
      >
        <Ionicons name="log-out-outline" size={18} color={colors.danger} />
        <Text style={[type.body, { color: colors.danger, fontWeight: "600" }]}>Sair da conta</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function MenuRow({
  icon,
  label,
  trailing,
  onPress,
  first,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  trailing?: string;
  onPress?: () => void;
  first?: boolean;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.7}
      style={{
        flexDirection: "row",
        alignItems: "center",
        padding: spacing.md,
        borderTopWidth: first ? 0 : 1,
        borderTopColor: colors.border,
      }}
    >
      <Ionicons name={icon} size={19} color={colors.textSecondary} style={{ marginRight: spacing.sm }} />
      <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]}>{label}</Text>
      {trailing ? (
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
          {trailing}
        </Text>
      ) : (
        <Ionicons name="chevron-forward" size={17} color={colors.textSecondary} />
      )}
    </TouchableOpacity>
  );
}
