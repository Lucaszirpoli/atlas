import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { Pressable, StyleSheet } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

// FAB do assistente, acessível em qualquer tela. Abre o assistente
// determinístico (livre, sem custo de token): responde sobre os dados do
// usuário e dúvidas de treino/dieta.
export function AiFab() {
  const { colors } = useTheme();
  const navigation = useNavigation<any>();

  return (
    <Pressable onPress={() => navigation.navigate("Assistant")} style={[styles.fab, { backgroundColor: colors.secondary }]}>
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
  badge: {
    position: "absolute",
    top: -2,
    right: -2,
    minWidth: 20,
    height: 20,
    borderRadius: 10,
    paddingHorizontal: 5,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "#FFFFFF",
  },
});
