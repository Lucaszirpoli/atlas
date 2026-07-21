import { Ionicons } from "@expo/vector-icons";
import { useHeaderHeight } from "@react-navigation/elements";
import React, { useRef, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { coachChat, type CoachChatMessage } from "../../api/coaching";
import { MarkdownText } from "../../components/MarkdownText";
import { useTheme } from "../../theme/ThemeProvider";

const GREETING =
  "Sou seu coach. Posso explicar sua análise da semana, sugerir o que priorizar e tirar dúvidas de treino, dieta e sono. O que você quer saber?";

const SUGGESTIONS = [
  "Por que você sugeriu isso?",
  "O que priorizar essa semana?",
  "Como acelerar meu resultado com segurança?",
  "Minha proteína está boa?",
];

/** "Pergunte ao coach" — a IA que EXPLICA a análise determinística. Não muda
 * plano (isso é o botão "Aplicar ajuste"); só conversa, ancorada nos números. */
export function CoachChatScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const insets = useSafeAreaInsets();
  const headerHeight = useHeaderHeight();
  const scrollRef = useRef<ScrollView>(null);

  const [messages, setMessages] = useState<CoachChatMessage[]>([
    { role: "assistant", content: GREETING },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setInput("");
    // história enviada = tudo menos a saudação inicial (é só enfeite).
    const history = messages.filter((m, i) => !(i === 0 && m.role === "assistant"));
    const next = [...messages, { role: "user", content: q } as CoachChatMessage];
    setMessages(next);
    setLoading(true);
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    try {
      const r = await coachChat(q, history);
      setMessages((m) => [...m, { role: "assistant", content: r.answer }]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", content: "Não consegui responder agora. Tenta de novo em instantes." },
      ]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={headerHeight}
    >
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.md }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        {messages.map((m, i) => (
          <View
            key={i}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "88%",
              backgroundColor: m.role === "user" ? colors.primary : colors.surface,
              borderRadius: radius.card,
              borderBottomRightRadius: m.role === "user" ? 4 : radius.card,
              borderBottomLeftRadius: m.role === "assistant" ? 4 : radius.card,
              paddingVertical: spacing.sm + 2,
              paddingHorizontal: spacing.md,
              marginBottom: spacing.sm,
              borderWidth: m.role === "assistant" ? 1 : 0,
              borderColor: colors.border,
            }}
          >
            {m.role === "assistant" ? (
              <MarkdownText content={m.content} color={colors.textPrimary} />
            ) : (
              <Text style={[type.body, { color: colors.textOnPrimary, lineHeight: 21 }]}>{m.content}</Text>
            )}
          </View>
        ))}
        {loading ? (
          <ActivityIndicator color={colors.textSecondary} style={{ alignSelf: "flex-start", marginTop: 4 }} />
        ) : null}

        {messages.length <= 1 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.sm }}>
            {SUGGESTIONS.map((s) => (
              <TouchableOpacity
                key={s}
                onPress={() => send(s)}
                style={{
                  backgroundColor: colors.surfaceAlt,
                  borderRadius: 999,
                  paddingVertical: 8,
                  paddingHorizontal: 12,
                  borderWidth: 1,
                  borderColor: colors.border,
                }}
              >
                <Text style={[type.caption, { color: colors.textPrimary }]}>{s}</Text>
              </TouchableOpacity>
            ))}
          </View>
        ) : null}
      </ScrollView>

      <View
        style={{
          flexDirection: "row",
          alignItems: "flex-end",
          gap: spacing.sm,
          padding: spacing.md,
          paddingBottom: spacing.md + insets.bottom,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          backgroundColor: colors.bg,
        }}
      >
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Pergunte ao seu coach..."
          placeholderTextColor={colors.textSecondary}
          multiline
          onSubmitEditing={() => send(input)}
          style={[
            type.body,
            {
              flex: 1,
              color: colors.textPrimary,
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: colors.border,
              paddingHorizontal: spacing.md,
              paddingTop: 10,
              paddingBottom: 10,
              maxHeight: 120,
            },
          ]}
        />
        <TouchableOpacity
          onPress={() => send(input)}
          disabled={!input.trim() || loading}
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            backgroundColor: input.trim() ? colors.primary : colors.surfaceAlt,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="arrow-up" size={22} color={input.trim() ? colors.textOnPrimary : colors.textSecondary} />
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
