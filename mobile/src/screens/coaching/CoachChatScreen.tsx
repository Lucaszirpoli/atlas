import { Ionicons } from "@expo/vector-icons";
import { useHeaderHeight } from "@react-navigation/elements";
import React, { useEffect, useRef, useState } from "react";
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

import { applyDiet, type DietPlan } from "../../api/ai";
import { coachChat } from "../../api/coaching";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { MarkdownText } from "../../components/MarkdownText";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { exportDietPdf } from "../../utils/dietPdf";
import { clearChat, loadChat, saveChat, type ChatBubble } from "./coachChatStore";

// Card do cardápio gerado pelo coach — totais + refeições, com botões de salvar
// em PDF e aplicar no diário de hoje.
function DietPlanCard({ plan }: { plan: DietPlan }) {
  const { colors, type, spacing, radius } = useTheme();
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const t = plan.totals;

  async function salvarPdf() {
    setErro(null);
    setPdfBusy(true);
    try {
      await exportDietPdf(plan);
    } catch {
      setErro("Não consegui gerar o PDF agora.");
    } finally {
      setPdfBusy(false);
    }
  }

  async function aplicar() {
    setErro(null);
    setApplying(true);
    try {
      await applyDiet(
        plan.meals.map((m) => ({
          category: m.category,
          items: m.items.map((it) => ({ food_id: it.food_id, quantity_g: it.quantity_g })),
        }))
      );
      setApplied(true);
    } catch {
      setErro("Não consegui aplicar no diário agora.");
    } finally {
      setApplying(false);
    }
  }

  return (
    <View
      style={{
        alignSelf: "flex-start",
        width: "96%",
        backgroundColor: colors.surface,
        borderRadius: radius.card,
        borderWidth: 1,
        borderColor: colors.border,
        padding: spacing.md,
        marginBottom: spacing.sm,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Ionicons name="restaurant-outline" size={16} color={colors.primary} />
        <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800", flex: 1 }]}>Sua dieta</Text>
      </View>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
        {Math.round(t.kcal)} kcal · P {Math.round(t.protein_g)}g · C {Math.round(t.carbs_g)}g · G {Math.round(t.fat_g)}g
      </Text>

      {plan.meals.map((m, i) => (
        <View key={i} style={{ marginBottom: spacing.sm }}>
          <Text style={[type.caption, { color: colors.primary, fontWeight: "700", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 2 }]}>
            {m.category}
          </Text>
          {m.items.map((it, j) => (
            <View key={j} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: 2 }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]} numberOfLines={1}>
                {it.food_name}
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginLeft: 8 }]}>
                {Math.round(it.quantity_g)} g · {Math.round(it.kcal)} kcal
              </Text>
            </View>
          ))}
        </View>
      ))}

      <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: 4 }}>
        <View style={{ flex: 1 }}>
          <Button
            title={pdfBusy ? "Gerando..." : "Salvar em PDF"}
            variant="secondary"
            compact
            loading={pdfBusy}
            onPress={salvarPdf}
          />
        </View>
        <View style={{ flex: 1 }}>
          {applied ? (
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, height: 40 }}>
              <Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>No diário</Text>
            </View>
          ) : (
            <Button title={applying ? "Aplicando..." : "Aplicar no diário"} compact loading={applying} onPress={aplicar} />
          )}
        </View>
      </View>
      {erro ? <Text style={[type.caption, { color: colors.warning, marginTop: 6 }]}>{erro}</Text> : null}
    </View>
  );
}

const GREETING =
  "Sou seu coach. Posso explicar sua análise e também AGIR: montar seu treino, trocar um exercício ou montar uma dieta pra você (dá pra salvar em PDF). É só pedir.";

const SUGGESTIONS = [
  "Monte meu treino",
  "Troca o agachamento por outro",
  "Monta uma dieta pra mim",
  "O que priorizar essa semana?",
];

/** "Pergunte ao coach" — a IA ancorada na análise determinística, com poder de
 * agir (montar treino, ajustar o plano, trocar exercício, gerar dieta).
 *
 * A conversa fica GUARDADA no aparelho (ver coachChatStore): sair da tela e
 * voltar apagava tudo, e junto ia o contexto que o coach usa pra entender a
 * próxima pergunta. */
export function CoachChatScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const { user } = useAuth();
  const insets = useSafeAreaInsets();
  const headerHeight = useHeaderHeight();
  const scrollRef = useRef<ScrollView>(null);

  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirmarLimpar, setConfirmarLimpar] = useState(false);
  // Enquanto a conversa antiga não chegou do storage, não se grava nada —
  // senão o estado vazio inicial sobrescreveria o que estava salvo.
  const [carregado, setCarregado] = useState(false);

  const chaveUsuario = user?.id ?? "anon";

  useEffect(() => {
    let cancelado = false;
    setCarregado(false);
    loadChat(chaveUsuario).then((antigas) => {
      if (cancelado) return;
      setMessages(antigas);
      setCarregado(true);
      // Volta no fim da conversa, como qualquer app de mensagem.
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: false }));
    });
    return () => {
      cancelado = true;
    };
  }, [chaveUsuario]);

  useEffect(() => {
    if (!carregado) return;
    saveChat(chaveUsuario, messages);
  }, [carregado, chaveUsuario, messages]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || loading) return;
    setInput("");
    // história enviada = só role/content (o servidor corta nas últimas 8).
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    try {
      const r = await coachChat(q, history);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: r.answer, actions: r.actions, dietPlan: r.diet_plan },
      ]);
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

  async function limparConversa() {
    await clearChat(chaveUsuario);
    setMessages([]);
    setConfirmarLimpar(false);
  }

  // A saudação é ENFEITE, não mensagem: aparece só na conversa vazia e nunca é
  // gravada nem mandada ao servidor como histórico.
  const bolhas: ChatBubble[] =
    messages.length === 0 ? [{ role: "assistant", content: GREETING }] : messages;

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={headerHeight}
    >
      {/* A conversa fica guardada neste aparelho. Quem guarda precisa oferecer
          como apagar — é dado de saúde (LGPD), e a pessoa manda nele. */}
      {messages.length > 0 ? (
        <TouchableOpacity
          onPress={() => setConfirmarLimpar(true)}
          accessibilityRole="button"
          accessibilityLabel="Apagar esta conversa"
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            paddingVertical: spacing.sm,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
          }}
        >
          <Ionicons name="time-outline" size={13} color={colors.textSecondary} />
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            Conversa salva neste aparelho · apagar
          </Text>
        </TouchableOpacity>
      ) : null}

      <ScrollView
        ref={scrollRef}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.md }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        {bolhas.map((m, i) => (
          <React.Fragment key={i}>
            <View
              style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "88%",
                backgroundColor: m.role === "user" ? colors.primary : colors.surface,
                borderRadius: radius.card,
                borderBottomRightRadius: m.role === "user" ? 4 : radius.card,
                borderBottomLeftRadius: m.role === "assistant" ? 4 : radius.card,
                paddingVertical: spacing.sm + 2,
                paddingHorizontal: spacing.md,
                marginBottom: m.actions?.length || m.dietPlan ? 6 : spacing.sm,
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

            {/* Confirmações do que o coach fez neste turno. */}
            {m.role === "assistant" && m.actions && m.actions.length > 0 ? (
              <View style={{ alignSelf: "flex-start", maxWidth: "92%", marginBottom: spacing.sm, gap: 4 }}>
                {m.actions.map((a, j) => (
                  <View key={j} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                    <Ionicons name="checkmark-circle" size={15} color={colors.success} />
                    <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>{a.summary}</Text>
                  </View>
                ))}
              </View>
            ) : null}

            {/* Cardápio gerado — ver, salvar em PDF ou aplicar no diário. */}
            {m.role === "assistant" && m.dietPlan ? <DietPlanCard plan={m.dietPlan} /> : null}
          </React.Fragment>
        ))}
        {loading ? (
          <ActivityIndicator color={colors.textSecondary} style={{ alignSelf: "flex-start", marginTop: 4 }} />
        ) : null}

        {messages.length === 0 ? (
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

      <ConfirmDialog
        visible={confirmarLimpar}
        onClose={() => setConfirmarLimpar(false)}
        title="Apagar esta conversa?"
        message={
          "As mensagens somem deste aparelho e o coach perde o contexto do que vocês " +
          "conversaram. O que ele já fez (treino montado, refeição registrada) continua valendo."
        }
        confirmLabel="Apagar"
        destructive
        onConfirm={limparConversa}
      />
    </KeyboardAvoidingView>
  );
}
