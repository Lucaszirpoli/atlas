import { Ionicons } from "@expo/vector-icons";
import React from "react";
import { Alert, Pressable, StyleSheet } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../theme/ThemeProvider";

// FAB de IA acessível em qualquer tela do app (espec. seção 3.6).
// A funcionalidade em si é exclusiva do plano Pro e chega na Fase 3/4.
export function AiFab() {
  const { colors } = useTheme();
  const { user } = useAuth();

  function handlePress() {
    if (user?.plan !== "pro") {
      Alert.alert(
        "Assistente de IA é exclusivo do Pro",
        "Assine o plano Pro para conversar com o assistente, registrar refeições por foto/voz e gerar treinos automaticamente."
      );
      return;
    }
    Alert.alert("Em breve", "O chat com a IA chega nas Fases 3 e 4 do roadmap.");
  }

  return (
    <Pressable
      onPress={handlePress}
      style={[styles.fab, { backgroundColor: colors.secondary }]}
    >
      <Ionicons name="sparkles" size={26} color="#FFFFFF" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: "absolute",
    right: 20,
    bottom: 84,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 4,
  },
});
