import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { Alert, Text, TouchableOpacity, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../theme/ThemeProvider";

/**
 * Entrada de IA embutida dentro de um módulo (Dieta, Treino...). É o mesmo
 * assistente do FAB global — só que aqui, no lugar certo, com um pedido já
 * pronto. Cumpre o diferencial do produto: recurso poderoso (montar dieta/
 * treino por IA), acesso em 1 toque, sem precisar entender nada antes.
 * O FAB global só existe no Dashboard, então dentro do módulo essa é a
 * única porta de entrada pra IA — sem duplicidade de "bolinhas".
 */
export function AiEntryCard({
  title,
  subtitle,
  prompt,
  destination,
}: {
  title: string;
  subtitle: string;
  /** Mensagem que já chega preenchida no chat, pronta pra enviar/editar. */
  prompt?: string;
  /** Destino alternativo (ex: o Hub de treino) em vez do chat. */
  destination?: { screen: string; params?: any };
}) {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const { user } = useAuth();
  const navigation = useNavigation<any>();

  const isPro = user?.plan === "pro";
  const credits = user?.ai_free_credits ?? 0;

  function handlePress() {
    if (destination) {
      navigation.navigate(destination.screen, destination.params);
      return;
    }
    if (!isPro && credits <= 0) {
      Alert.alert(
        "Assistente de IA — Pro",
        "Suas mensagens grátis acabaram. Assine o Pro para montar dieta e treino por IA sem limite."
      );
      return;
    }
    navigation.navigate("Chat", { prefill: prompt });
  }

  return (
    <TouchableOpacity activeOpacity={0.88} onPress={handlePress} style={{ marginBottom: spacing.md }}>
      <View
        style={[
          {
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.secondary,
            borderRadius: radius.card,
            padding: spacing.md,
          },
          shadow.sm,
        ]}
      >
        <View
          style={{
            width: 44,
            height: 44,
            borderRadius: 15,
            backgroundColor: "rgba(255,255,255,0.22)",
            alignItems: "center",
            justifyContent: "center",
            marginRight: spacing.md,
          }}
        >
          <Ionicons name="sparkles" size={22} color="#FFFFFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.h2, { color: "#FFFFFF", fontSize: 16 }]}>{title}</Text>
          <Text style={[type.caption, { color: "rgba(255,255,255,0.88)" }]} numberOfLines={2}>
            {subtitle}
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
      </View>
    </TouchableOpacity>
  );
}
