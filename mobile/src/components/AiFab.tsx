import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useTheme } from "../theme/ThemeProvider";

// FAB de IA acessível em qualquer tela (espec. 3.6). O Free entra e prova a
// IA com créditos grátis (isca); ao esgotar, o chat oferece o Pro.
export function AiFab() {
  const { colors, type } = useTheme();
  const { user } = useAuth();
  const navigation = useNavigation<any>();

  const isPro = user?.plan === "pro";
  const credits = user?.ai_free_credits ?? 0;

  function handlePress() {
    if (!isPro && credits <= 0) {
      Alert.alert(
        "Assistente de IA — Pro",
        "Suas mensagens grátis acabaram. Assine o Pro para conversar sem limite, montar treino por IA e registrar refeição por foto."
      );
      return;
    }
    navigation.navigate("Chat");
  }

  return (
    <Pressable onPress={handlePress} style={[styles.fab, { backgroundColor: colors.secondary }]}>
      <Ionicons name="sparkles" size={26} color="#FFFFFF" />
      {!isPro && credits > 0 ? (
        <View style={[styles.badge, { backgroundColor: colors.primary }]}>
          <Text style={{ color: "#FFFFFF", fontSize: 11, fontWeight: "800" }}>{credits}</Text>
        </View>
      ) : null}
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
