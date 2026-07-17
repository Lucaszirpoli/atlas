import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { blockUser } from "../../api/blocksAndReports";
import {
  acceptFriendRequest,
  declineFriendRequest,
  listFriendRequests,
  listFriends,
  sendFriendRequest,
  type FriendRequest,
  type UserSummary,
} from "../../api/friends";
import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";

export function FriendsScreen() {
  const { colors, type, spacing, radius } = useTheme();

  const [friends, setFriends] = useState<UserSummary[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [handleInput, setHandleInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  async function load() {
    const [f, r] = await Promise.all([listFriends(), listFriendRequests()]);
    setFriends(f);
    setRequests(r);
  }

  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  async function handleSendRequest() {
    if (!handleInput.trim()) return;
    setIsSending(true);
    try {
      // Só o envio no try: o load() ficava aqui e, se falhasse, o catch dizia
      // "não foi possível enviar" com o pedido JÁ enviado — a pessoa mandava
      // de novo e o amigo recebia dois convites.
      await sendFriendRequest(handleInput.trim().toLowerCase().replace(/^@/, ""));
    } catch (err: any) {
      Alert.alert("Não foi possível enviar", err?.response?.data?.detail ?? "Tente novamente.");
      setIsSending(false);
      return;
    }
    setHandleInput("");
    // Recarregar a lista é cosmético: falhou, a próxima abertura da tela pega.
    await load().catch(() => {});
    setIsSending(false);
  }

  const receivedRequests = requests.filter((r) => r.direction === "received");
  const sentRequests = requests.filter((r) => r.direction === "sent");

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Adicionar */}
      <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg }}>
        <View
          style={{
            flex: 1,
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.surface,
            borderRadius: radius.pill,
            paddingHorizontal: spacing.md,
            height: 50,
            borderWidth: 1,
            borderColor: colors.border,
          }}
        >
          <Text style={[type.body, { color: colors.textSecondary }]}>@</Text>
          <TextInput
            value={handleInput}
            onChangeText={setHandleInput}
            autoCapitalize="none"
            placeholder="handle do amigo"
            placeholderTextColor={colors.textSecondary}
            style={[type.body, { flex: 1, color: colors.textPrimary, marginLeft: 4, height: "100%" }]}
          />
        </View>
        <TouchableOpacity
          onPress={handleSendRequest}
          disabled={isSending}
          activeOpacity={0.8}
          style={{
            width: 50,
            height: 50,
            borderRadius: 25,
            backgroundColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
            opacity: isSending ? 0.6 : 1,
          }}
        >
          <Ionicons name="person-add" size={20} color={colors.textOnPrimary} />
        </TouchableOpacity>
      </View>

      {/* Pedidos recebidos */}
      {receivedRequests.length > 0 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Pedidos recebidos
          </Text>
          {receivedRequests.map((r) => (
            <Card key={r.id} style={{ marginBottom: spacing.sm }}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Avatar name={r.other_user.display_name} handle={r.other_user.handle} />
                <View style={{ flex: 1, marginLeft: spacing.sm }}>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
                    {r.other_user.display_name}
                  </Text>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>@{r.other_user.handle}</Text>
                </View>
                <TouchableOpacity
                  onPress={async () => {
                    await acceptFriendRequest(r.id);
                    load();
                  }}
                  style={{
                    backgroundColor: colors.primary,
                    borderRadius: radius.pill,
                    paddingVertical: 8,
                    paddingHorizontal: 16,
                    marginRight: spacing.xs,
                  }}
                >
                  <Text style={[type.caption, { color: colors.textOnPrimary, fontWeight: "700" }]}>Aceitar</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={async () => {
                    await declineFriendRequest(r.id);
                    load();
                  }}
                  hitSlop={8}
                >
                  <Ionicons name="close-circle" size={26} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            </Card>
          ))}
        </>
      ) : null}

      {sentRequests.length > 0 ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
          Aguardando resposta: {sentRequests.map((r) => `@${r.other_user.handle}`).join(", ")}
        </Text>
      ) : null}

      {/* Amigos */}
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Meus amigos ({friends.length})
      </Text>
      {friends.length === 0 ? (
        <Card>
          <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", paddingVertical: spacing.sm }]}>
            Você ainda não tem amigos por aqui.{"\n"}Adicione pelo @handle acima.
          </Text>
        </Card>
      ) : (
        <Card padded={false}>
          {friends.map((item, i) => (
            <TouchableOpacity
              key={item.id}
              onLongPress={() =>
                Alert.alert(item.display_name, undefined, [
                  {
                    text: "Bloquear",
                    style: "destructive",
                    onPress: async () => {
                      await blockUser(item.handle);
                      load();
                    },
                  },
                  { text: "Cancelar", style: "cancel" },
                ])
              }
              style={{
                flexDirection: "row",
                alignItems: "center",
                padding: spacing.md,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.border,
              }}
            >
              <Avatar name={item.display_name} handle={item.handle} size={44} />
              <View style={{ marginLeft: spacing.sm }}>
                <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{item.display_name}</Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>@{item.handle}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </Card>
      )}
    </ScrollView>
  );
}
