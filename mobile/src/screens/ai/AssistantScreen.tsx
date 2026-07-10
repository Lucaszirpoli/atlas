import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import type { ProposedAction } from "../../api/ai";
import { getChatHistory } from "../../api/ai";
import { askAssistant } from "../../api/assistant";
import { ChatActionCard } from "../../components/ChatActionCard";
import { useTheme } from "../../theme/ThemeProvider";

type Msg = {
  role: "user" | "assistant";
  text: string;
  fromAi?: boolean;
  proposedAction?: ProposedAction | null;
  resolvedAction?: "confirmed" | "cancelled";
};

const GREETING: Msg = {
  role: "assistant",
  text: "Oi! Sou seu assistente. Posso responder sobre seus dados (calorias, proteína, peso, água, sono, treinos) e tirar dúvidas de treino/dieta. Pergunte algo ou toque numa sugestão abaixo. 👇",
};

const SUGGESTIONS = [
  "Quantas calorias comi hoje?",
  "Quanta proteína comi?",
  "Quanto tô pesando?",
  "Quantos treinos fiz essa semana?",
  "O que é RIR?",
  "Como registro comida?",
];

export function AssistantScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const scrollRef = useRef<ScrollView>(null);

  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // Recupera a conversa com a IA ao reabrir a tela (mesmo histórico usado
  // pela IA pra manter contexto entre mensagens) — sem isso, sair e voltar
  // fazia a conversa (e qualquer proposta em aberto) sumir da tela. Propostas
  // antigas só aparecem como texto aqui (não reabrimos o card de confirmação
  // pra evitar confirmar de novo algo que já foi resolvido antes).
  useEffect(() => {
    getChatHistory()
      .then((history) => {
        if (history.length === 0) return;
        setMessages([
          GREETING,
          ...history.map((h) => ({ role: h.role, text: h.content, fromAi: h.role === "assistant" })),
        ]);
        requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: false }));
      })
      .catch(() => {});
  }, []);

  async function send(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    try {
      const r = await askAssistant(q);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: r.reply, fromAi: r.source === "ai", proposedAction: r.proposed_action },
      ]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Ops, não consegui responder agora. Tente de novo." }]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    }
  }

  function resolveAction(index: number, outcome: "confirmed" | "cancelled") {
    setMessages((m) => m.map((msg, i) => (i === index ? { ...msg, resolvedAction: outcome } : msg)));
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.md }}
        keyboardShouldPersistTaps="handled"
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
            <Text style={[type.body, { color: m.role === "user" ? colors.textOnPrimary : colors.textPrimary, lineHeight: 21 }]}>
              {m.text}
            </Text>
            {m.fromAi ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: 6 }}>
                <Ionicons name="sparkles" size={11} color={colors.secondary} />
                <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>respondido pela IA</Text>
              </View>
            ) : null}
            {m.proposedAction && !m.resolvedAction ? (
              <ChatActionCard action={m.proposedAction} onResolved={(outcome) => resolveAction(i, outcome)} />
            ) : null}
            {m.resolvedAction === "confirmed" ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: spacing.xs }}>
                <Ionicons name="checkmark-circle" size={14} color={colors.primary} />
                <Text style={[type.caption, { color: colors.primary }]}>Confirmado</Text>
              </View>
            ) : null}
          </View>
        ))}
        {loading ? <ActivityIndicator color={colors.textSecondary} style={{ alignSelf: "flex-start", marginTop: 4 }} /> : null}

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
          borderTopWidth: 1,
          borderTopColor: colors.border,
          backgroundColor: colors.bg,
        }}
      >
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Pergunte algo... (ou use o 🎙️ do teclado)"
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
    </View>
  );
}
