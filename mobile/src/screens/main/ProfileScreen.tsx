import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import * as ImagePicker from "expo-image-picker";
import React, { useCallback, useState } from "react";
import { Alert, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { deleteAccount } from "../../api/auth";
import { syncPlan } from "../../api/billing";
import { resetAppData } from "../../api/profile";
import { configurePurchases, getEntitlementActive, isNativePurchasesAvailable } from "../../api/purchases";
import { ActionSheet, type ActionSheetOption } from "../../components/ActionSheet";
import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme, type ThemeMode } from "../../theme/ThemeProvider";
import { useProfilePhoto } from "../../utils/profilePhoto";

export function ProfileScreen() {
  const { colors, type, spacing, shadow, mode, setMode } = useTheme();
  const navigation = useNavigation<any>();
  const { user, signOut, refreshUser } = useAuth();
  const profilePhoto = useProfilePhoto();
  const [showPhotoMenu, setShowPhotoMenu] = useState(false);
  // Resetar dados: confirmação -> execução -> resumo do que saiu.
  const [confirmarReset, setConfirmarReset] = useState(false);
  const [resetando, setResetando] = useState(false);
  const [resultadoReset, setResultadoReset] = useState<string | null>(null);
  // Excluir conta: exigido pela App Store (quem cria conta pelo app tem que
  // conseguir apagar pelo app) — ver DELETE /users/me, que apaga em cascata.
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);
  const [excluindo, setExcluindo] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);

  async function executarReset() {
    setConfirmarReset(false);
    setResetando(true);
    try {
      const r = await resetAppData();
      const linhas = Object.entries(r.apagados).map(([k, v]) => `${v} ${k}`);
      setResultadoReset(
        linhas.length
          ? `Apaguei ${linhas.join(", ")}. Sua conta e seu plano continuam iguais.`
          : "Não havia nada registrado pra apagar."
      );
      // O perfil e o questionário também foram apagados — sem recarregar o
      // usuário, o app continuaria achando que o onboarding está completo.
      await refreshUser().catch(() => {});
    } catch {
      setResultadoReset("Não consegui apagar agora. Seus dados continuam como estavam — tente de novo.");
    } finally {
      setResetando(false);
    }
  }

  async function executarExclusao() {
    setConfirmarExclusao(false);
    setExcluindo(true);
    try {
      await deleteAccount();
      await signOut();
    } catch {
      setErroExclusao("Não consegui excluir sua conta agora. Tente de novo em instantes.");
    } finally {
      setExcluindo(false);
    }
  }

  async function escolherFoto() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permissão necessária", "Precisamos acessar suas fotos para isso.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.8, allowsEditing: true, aspect: [1, 1] });
    if (result.canceled || !result.assets[0]) return;
    await profilePhoto.escolher(result.assets[0].uri);
  }

  const photoMenuOptions: ActionSheetOption[] = [
    { label: profilePhoto.uri ? "Trocar foto" : "Escolher foto", onPress: escolherFoto },
    ...(profilePhoto.uri
      ? [{ label: "Remover foto", destructive: true, onPress: () => profilePhoto.remover() }]
      : []),
  ];

  // Sempre que a tela ganha foco, revalida o plano — assim, se a compra do Pro
  // foi confirmada pelo webhook depois que a pessoa saiu do paywall, o status
  // Pro aparece aqui sem precisar reabrir o app.
  //
  // O sync com a LOJA (getEntitlementActive) morou no boot/login até a v20 —
  // rodava pra todo mundo, na cara do primeiro login, e é suspeito de causar
  // tela branca em conta nova (crash nativo do RevenueCat, não capturável por
  // try/catch). Mudou pra cá: só quem abre o Perfil toca no SDK nativo, bem
  // longe da janela crítica de quem acabou de criar conta.
  useFocusEffect(
    useCallback(() => {
      refreshUser().catch(() => {});
      if (user && user.plan !== "pro" && isNativePurchasesAvailable()) {
        try {
          configurePurchases(String(user.id));
          getEntitlementActive()
            .then((active) => {
              if (active) {
                syncPlan(true).then(() => refreshUser()).catch(() => {});
              }
            })
            .catch(() => {});
        } catch {
          // RevenueCat indisponível neste aparelho — o Perfil segue normal.
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, user?.plan])
  );

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingTop: spacing.xl + spacing.md, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Cabeçalho do perfil */}
      <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
        <TouchableOpacity onPress={() => setShowPhotoMenu(true)} activeOpacity={0.85}>
          <Avatar
            name={user?.display_name ?? "?"}
            handle={user?.handle ?? "?"}
            size={86}
            photoUri={profilePhoto.uri}
          />
          <View
            style={{
              position: "absolute",
              right: -2,
              bottom: -2,
              width: 28,
              height: 28,
              borderRadius: 14,
              backgroundColor: colors.primary,
              borderWidth: 2,
              borderColor: colors.bg,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Ionicons name="camera" size={13} color={colors.textOnPrimary} />
          </View>
        </TouchableOpacity>
        <Text style={[type.h1, { color: colors.textPrimary, marginTop: spacing.md }]}>
          {user?.display_name}
        </Text>
        <Text style={[type.body, { color: colors.textSecondary }]}>@{user?.handle}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          Foto salva só neste aparelho — ainda não aparece pros seus amigos
        </Text>
      </View>

      <ActionSheet
        visible={showPhotoMenu}
        onClose={() => setShowPhotoMenu(false)}
        title="Foto de perfil"
        options={photoMenuOptions}
      />

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
                ? "Coaching, assistente de IA ilimitado e treino/dieta por IA"
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
              { key: "dark", label: "Escuro", icon: "moon-outline" },
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
                  ...(active ? shadow.sm : {}),
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
        {user?.plan === "pro" ? (
          <MenuRow
            icon="swap-vertical"
            label="Layout da tela inicial"
            onPress={() => navigation.navigate("HomeLayout")}
            first
          />
        ) : null}
        <MenuRow icon="trending-up-outline" label="Evolução" onPress={() => navigation.navigate("Evolution")} first={user?.plan !== "pro"} />
        <MenuRow icon="moon-outline" label="Sono" onPress={() => navigation.navigate("Sleep")} />
        <MenuRow icon="mail" label="E-mail" trailing={user?.email} />
        <MenuRow
          icon="refresh-outline"
          label={resetando ? "Apagando..." : "Resetar dados do app"}
          onPress={resetando ? undefined : () => setConfirmarReset(true)}
        />
      </Card>

      <TouchableOpacity
        onPress={signOut}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: spacing.md }}
      >
        <Ionicons name="log-out-outline" size={18} color={colors.danger} />
        <Text style={[type.body, { color: colors.danger, fontWeight: "600" }]}>Sair da conta</Text>
      </TouchableOpacity>

      <TouchableOpacity
        onPress={excluindo ? undefined : () => setConfirmarExclusao(true)}
        activeOpacity={0.7}
        style={{ alignItems: "center", paddingVertical: spacing.sm }}
      >
        <Text style={[type.caption, { color: colors.textSecondary }]}>
          {excluindo ? "Excluindo conta..." : "Excluir minha conta"}
        </Text>
      </TouchableOpacity>

      <ConfirmDialog
        visible={confirmarExclusao}
        title="Excluir sua conta?"
        message={
          "Isso apaga sua conta, seu login e TODO o seu histórico (refeições, treinos, peso, sono, " +
          "medidas, posts e conexões) para sempre. Não tem como desfazer."
        }
        confirmLabel="Excluir conta"
        destructive
        onClose={() => setConfirmarExclusao(false)}
        onConfirm={executarExclusao}
      />
      <InfoDialog
        visible={erroExclusao !== null}
        title="Não foi possível excluir"
        message={erroExclusao ?? undefined}
        onClose={() => setErroExclusao(null)}
      />

      {/* Recomeçar do zero sem perder a conta. Quem testou o app por semanas
          antes de começar pra valer ficava com gráficos que descrevem os testes,
          não a vida dela — e a única saída era criar outra conta. */}
      <ConfirmDialog
        visible={confirmarReset}
        title="Resetar dados do app?"
        message={
          "Apaga TODO o seu histórico: refeições, treinos, peso, sono, medidas, metas e os planos do " +
          "coach. Sua conta, seu e-mail e seu plano continuam. Isso não tem como desfazer."
        }
        confirmLabel="Apagar tudo"
        destructive
        onClose={() => setConfirmarReset(false)}
        onConfirm={executarReset}
      />
      <InfoDialog
        visible={resultadoReset !== null}
        title="Pronto"
        message={resultadoReset ?? undefined}
        onClose={() => setResultadoReset(null)}
      />
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
