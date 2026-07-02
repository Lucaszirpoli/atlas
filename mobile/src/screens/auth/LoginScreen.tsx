import { useNavigation } from "@react-navigation/native";
import React, { useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";

import { Button } from "../../components/Button";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

export function LoginScreen() {
  const { colors, type, spacing } = useTheme();
  const { signIn } = useAuth();
  const navigation = useNavigation<any>();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setIsSubmitting(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
    } catch (err: any) {
      Alert.alert(
        "Não foi possível entrar",
        err?.response?.data?.detail ?? "Verifique seus dados e tente novamente."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView
      contentContainerStyle={{
        flexGrow: 1,
        justifyContent: "center",
        padding: spacing.lg,
        backgroundColor: colors.bg,
      }}
    >
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.lg }]}>
        Bem-vindo de volta
      </Text>

      <TextField
        label="E-mail"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextField
        label="Senha"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <Button title="Entrar" onPress={handleSubmit} loading={isSubmitting} />

      <View style={{ marginTop: spacing.lg }}>
        <Button
          title="Ainda não tenho conta"
          variant="ghost"
          onPress={() => navigation.navigate("Register")}
        />
      </View>
    </ScrollView>
  );
}
