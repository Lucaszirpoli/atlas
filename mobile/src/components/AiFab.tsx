import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { Alert, Pressable, StyleSheet } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../theme/ThemeProvider";

// FAB de IA acessível em qualquer tela do app (espec. seção 3.6).
export function AiFab() {
  const { colors } = useTheme();
  const { user } = useAuth();
  const navigation = useNavigation<any>();

  function handlePress() {
    if (user?.plan !== "pro") {
      Alert.alert(
        "Assistente de IA é exclusivo do Pro",
        "Assine o plano Pro para conversar com o assistente, registrar refeições por foto/voz e gerar treinos automaticamente."
      );
      return;
    }
    navigation.navigate("Chat");
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
