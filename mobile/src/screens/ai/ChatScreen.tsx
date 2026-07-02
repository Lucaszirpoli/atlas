import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { getChatHistory, sendChatMessage, type ChatMessage, type ProposedAction } from "../../api/ai";
import { ChatActionCard } from "../../components/ChatActionCard";
import { useTheme } from "../../theme/ThemeProvider";

type DisplayMessage = ChatMessage & { resolvedAction?: "confirmed" | "cancelled" };

export function ChatScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const listRef = useRef<FlatList>(null);

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  useEffect(() => {
    getChatHistory()
      .then(setMessages)
      .finally(() => setIsLoadingHistory(false));
  }, []);

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;
    setInput("");
    setIsSending(true);

    const optimisticUser: DisplayMessage = {
      id: Date.now(),
      role: "user",
      content: text,
      proposed_action: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      const response = await sendChatMessage(text);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: response.reply,
          proposed_action: response.proposed_action,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      Alert.alert("Não foi possível enviar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSending(false);
    }
  }

  function resolveAction(messageId: number, outcome: "confirmed" | "cancelled") {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, resolvedAction: outcome } : m)));
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          padding: spacing.md,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
        }}
      >
        <Text style={[type.h2, { color: colors.textPrimary }]}>Assistente appfit</Text>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={[type.body, { color: colors.primary }]}>Fechar</Text>
        </TouchableOpacity>
      </View>

      {isLoadingHistory ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} />
      ) : (
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={{ padding: spacing.lg }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          renderItem={({ item }) => (
            <View
              style={{
                alignSelf: item.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "85%",
                marginBottom: spacing.md,
              }}
            >
              <View
                style={{
                  backgroundColor: item.role === "user" ? colors.primaryLight + "33" : colors.surface,
                  borderWidth: item.role === "assistant" ? 1 : 0,
                  borderColor: colors.border,
                  borderRadius: 16,
                  padding: spacing.sm,
                }}
              >
                <Text style={[type.body, { color: colors.textPrimary }]}>{item.content}</Text>
              </View>
              {item.proposed_action && !item.resolvedAction ? (
                <ChatActionCard
                  action={item.proposed_action}
                  onResolved={(outcome) => resolveAction(item.id, outcome)}
                />
              ) : null}
              {item.resolvedAction === "confirmed" ? (
                <Text style={[type.caption, { color: colors.success, marginTop: spacing.xs }]}>
                  Confirmado ✓
                </Text>
              ) : null}
            </View>
          )}
        />
      )}

      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          padding: spacing.md,
          borderTopWidth: 1,
          borderTopColor: colors.border,
        }}
      >
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Pergunte ou registre uma refeição..."
          placeholderTextColor={colors.textSecondary}
          style={[
            type.body,
            {
              flex: 1,
              color: colors.textPrimary,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.button,
              paddingHorizontal: spacing.md,
              height: 44,
              marginRight: spacing.sm,
            },
          ]}
        />
        <TouchableOpacity
          onPress={handleSend}
          disabled={isSending}
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            backgroundColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
            opacity: isSending ? 0.6 : 1,
          }}
        >
          <Text style={{ color: "#FFFFFF" }}>➤</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
