import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
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

import { getChatHistory, sendChatMessage, type ChatMessage } from "../../api/ai";
import { ChatActionCard } from "../../components/ChatActionCard";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

type DisplayMessage = ChatMessage & { resolvedAction?: "confirmed" | "cancelled"; isError?: boolean };

const SUGGESTIONS = [
  "Comi 2 ovos e uma banana no café",
  "Monta um treino de 4 dias pra mim",
  "Como foi minha semana de treinos?",
];

export function ChatScreen() {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { user, refreshUser } = useAuth();
  const listRef = useRef<FlatList>(null);

  const isPro = user?.plan === "pro";
  const [credits, setCredits] = useState(user?.ai_free_credits ?? 0);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  // Quando aberto a partir de um card embutido (ex: "Monte sua dieta com IA"
  // na tela de Dieta), o pedido já chega pronto no campo — só falta enviar.
  const [input, setInput] = useState(() => route.params?.prefill ?? "");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  useEffect(() => {
    getChatHistory()
      .then(setMessages)
      .finally(() => setIsLoadingHistory(false));
  }, []);

  async function handleSend(textOverride?: string) {
    const text = (textOverride ?? input).trim();
    if (!text || isSending) return;
    setInput("");
    setIsSending(true);

    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content: text, proposed_action: null, created_at: new Date().toISOString() },
    ]);

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
      if (!isPro && response.free_credits_remaining != null) {
        setCredits(response.free_credits_remaining);
        refreshUser().catch(() => {}); // sincroniza o badge do FAB
      }
    } catch (err: any) {
      // Alert não aparece na web — mostramos o erro como bolha no próprio chat.
      const detail =
        err?.response?.data?.detail ??
        "Não consegui falar com o servidor. Verifique sua conexão e tente de novo.";
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          content: detail,
          proposed_action: null,
          created_at: new Date().toISOString(),
          isError: true,
        },
      ]);
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
      {/* Header */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          padding: spacing.md,
          paddingHorizontal: spacing.lg,
          backgroundColor: colors.surface,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
        }}
      >
        <View
          style={{
            width: 40,
            height: 40,
            borderRadius: 14,
            backgroundColor: colors.secondary,
            alignItems: "center",
            justifyContent: "center",
            marginRight: spacing.sm,
          }}
        >
          <Ionicons name="sparkles" size={20} color={colors.textOnPrimary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 17 }]}>Assistente appfit</Text>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            Nutrição, treino e sono — num chat só
          </Text>
        </View>
        <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={10}>
          <Ionicons name="close" size={24} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {/* Banner de isca — só para Free */}
      {!isPro ? (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            paddingVertical: spacing.sm,
            paddingHorizontal: spacing.lg,
            backgroundColor: credits > 0 ? colors.primarySoft : colors.secondarySoft,
          }}
        >
          <Ionicons
            name={credits > 0 ? "gift" : "lock-closed"}
            size={15}
            color={credits > 0 ? colors.primary : colors.secondary}
          />
          <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
            {credits > 0
              ? `Você tem ${credits} ${credits === 1 ? "mensagem grátis" : "mensagens grátis"} para testar a IA`
              : "Suas mensagens grátis acabaram — assine o Pro para continuar"}
          </Text>
          <TouchableOpacity onPress={() => navigation.navigate("Profile")}>
            <Text style={[type.caption, { color: colors.secondary, fontWeight: "800" }]}>Ver Pro</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {isLoadingHistory ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} />
      ) : messages.length === 0 ? (
        /* Estado vazio com sugestões */
        <View style={{ flex: 1, justifyContent: "center", padding: spacing.lg }}>
          <Text style={[type.h1, { color: colors.textPrimary, textAlign: "center", marginBottom: spacing.xs }]}>
            Oi! 👋
          </Text>
          <Text style={[type.body, { color: colors.textSecondary, textAlign: "center", marginBottom: spacing.xl }]}>
            Posso registrar refeições, montar treinos{"\n"}e analisar sua evolução. Experimente:
          </Text>
          {SUGGESTIONS.map((s) => (
            <TouchableOpacity
              key={s}
              onPress={() => handleSend(s)}
              activeOpacity={0.7}
              style={[
                {
                  backgroundColor: colors.surface,
                  borderRadius: radius.card,
                  padding: spacing.md,
                  marginBottom: spacing.sm,
                  flexDirection: "row",
                  alignItems: "center",
                },
                shadow.sm,
              ]}
            >
              <Ionicons name="chatbubble-ellipses-outline" size={17} color={colors.secondary} style={{ marginRight: spacing.sm }} />
              <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>{s}</Text>
            </TouchableOpacity>
          ))}
        </View>
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
                  backgroundColor: item.isError
                    ? colors.danger + "14"
                    : item.role === "user"
                      ? colors.primary
                      : colors.surface,
                  borderWidth: item.role === "assistant" ? 1 : 0,
                  borderColor: item.isError ? colors.danger : colors.border,
                  borderRadius: 18,
                  borderBottomRightRadius: item.role === "user" ? 6 : 18,
                  borderBottomLeftRadius: item.role === "assistant" ? 6 : 18,
                  paddingVertical: spacing.sm + 2,
                  paddingHorizontal: spacing.md,
                }}
              >
                {item.isError ? (
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginBottom: 2 }}>
                    <Ionicons name="warning" size={13} color={colors.danger} />
                    <Text style={[type.caption, { color: colors.danger, fontWeight: "700" }]}>
                      Não deu certo
                    </Text>
                  </View>
                ) : null}
                <Text style={[type.body, { color: item.role === "user" ? colors.textOnPrimary : colors.textPrimary }]}>
                  {item.content}
                </Text>
              </View>
              {item.proposed_action && !item.resolvedAction ? (
                <ChatActionCard action={item.proposed_action} onResolved={(outcome) => resolveAction(item.id, outcome)} />
              ) : null}
              {item.resolvedAction === "confirmed" ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: spacing.xs }}>
                  <Ionicons name="checkmark-circle" size={14} color={colors.success} />
                  <Text style={[type.caption, { color: colors.success }]}>Confirmado</Text>
                </View>
              ) : null}
            </View>
          )}
        />
      )}

      {isSending ? (
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.lg, paddingBottom: spacing.xs, gap: 6 }}>
          <ActivityIndicator size="small" color={colors.secondary} />
          <Text style={[type.caption, { color: colors.textSecondary }]}>pensando...</Text>
        </View>
      ) : null}

      {/* Input */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          padding: spacing.md,
          paddingHorizontal: spacing.lg,
          backgroundColor: colors.surface,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          gap: spacing.sm,
        }}
      >
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Pergunte ou registre uma refeição..."
          placeholderTextColor={colors.textSecondary}
          onSubmitEditing={() => handleSend()}
          style={[
            type.body,
            {
              flex: 1,
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.pill,
              paddingHorizontal: spacing.md,
              height: 48,
            },
          ]}
        />
        <TouchableOpacity
          onPress={() => handleSend()}
          disabled={isSending}
          activeOpacity={0.8}
          style={{
            width: 48,
            height: 48,
            borderRadius: 24,
            backgroundColor: colors.secondary,
            alignItems: "center",
            justifyContent: "center",
            opacity: isSending ? 0.6 : 1,
          }}
        >
          <Ionicons name="arrow-up" size={22} color={colors.textOnPrimary} />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
