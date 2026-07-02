import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

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
import { Button } from "../../components/Button";
import { TextField } from "../../components/TextField";
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
      await sendFriendRequest(handleInput.trim().toLowerCase());
      setHandleInput("");
      await load();
    } catch (err: any) {
      Alert.alert("Não foi possível enviar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSending(false);
    }
  }

  const receivedRequests = requests.filter((r) => r.direction === "received");
  const sentRequests = requests.filter((r) => r.direction === "sent");

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>Amigos</Text>

      <TextField
        label="Adicionar por @handle"
        autoCapitalize="none"
        value={handleInput}
        onChangeText={setHandleInput}
      />
      <Button title="Enviar pedido" onPress={handleSendRequest} loading={isSending} />

      {receivedRequests.length > 0 ? (
        <View style={{ marginTop: spacing.lg }}>
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
            Pedidos recebidos
          </Text>
          {receivedRequests.map((r) => (
            <View
              key={r.id}
              style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.xs }}
            >
              <Text style={[type.body, { color: colors.textPrimary }]}>@{r.other_user.handle}</Text>
              <View style={{ flexDirection: "row", gap: spacing.sm }}>
                <TouchableOpacity onPress={async () => { await acceptFriendRequest(r.id); load(); }}>
                  <Text style={[type.bodySmall, { color: colors.success }]}>Aceitar</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={async () => { await declineFriendRequest(r.id); load(); }}>
                  <Text style={[type.bodySmall, { color: colors.danger }]}>Recusar</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {sentRequests.length > 0 ? (
        <View style={{ marginTop: spacing.md }}>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            Pedidos enviados: {sentRequests.map((r) => `@${r.other_user.handle}`).join(", ")}
          </Text>
        </View>
      ) : null}

      <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
        Meus amigos
      </Text>
      <FlatList
        data={friends}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
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
              paddingVertical: spacing.sm,
              borderBottomWidth: 1,
              borderBottomColor: colors.border,
            }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{item.display_name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>@{item.handle}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
            Você ainda não tem amigos por aqui.
          </Text>
        }
      />
    </View>
  );
}
