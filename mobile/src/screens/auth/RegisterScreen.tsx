import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";

import { checkHandleAvailability } from "../../api/auth";
import { Button } from "../../components/Button";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const HANDLE_PATTERN = /^[a-z0-9_]{3,30}$/;

export function RegisterScreen() {
  const { colors, type, spacing } = useTheme();
  const { signUp } = useAuth();
  const navigation = useNavigation<any>();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [handle, setHandle] = useState("");
  const [handleStatus, setHandleStatus] = useState<
    "idle" | "checking" | "available" | "taken" | "invalid"
  >("idle");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (handle.length === 0) {
      setHandleStatus("idle");
      return;
    }
    if (!HANDLE_PATTERN.test(handle)) {
      setHandleStatus("invalid");
      return;
    }
    setHandleStatus("checking");
    const timeout = setTimeout(async () => {
      try {
        const result = await checkHandleAvailability(handle);
        setHandleStatus(result.available ? "available" : "taken");
      } catch {
        setHandleStatus("idle");
      }
    }, 400);
    return () => clearTimeout(timeout);
  }, [handle]);

  const handleHint =
    handleStatus === "invalid"
      ? "3-30 caracteres: letras minúsculas, números ou _"
      : handleStatus === "taken"
        ? "Esse @handle já está em uso"
        : handleStatus === "available"
          ? "Disponível!"
          : undefined;

  async function handleSubmit() {
    if (handleStatus !== "available") {
      Alert.alert("Verifique o @handle", "Escolha um @handle válido e disponível.");
      return;
    }
    setIsSubmitting(true);
    try {
      await signUp({
        email: email.trim().toLowerCase(),
        password,
        handle,
        display_name: displayName.trim(),
      });
    } catch (err: any) {
      Alert.alert(
        "Não foi possível criar sua conta",
        err?.response?.data?.detail ?? "Tente novamente em instantes."
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
        Criar conta
      </Text>

      <TextField label="Nome de exibição" value={displayName} onChangeText={setDisplayName} />
      <TextField
        label="@handle"
        autoCapitalize="none"
        value={handle}
        onChangeText={(v) => setHandle(v.toLowerCase())}
        error={handleHint}
      />
      <TextField
        label="E-mail"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextField label="Senha" secureTextEntry value={password} onChangeText={setPassword} />

      <Button title="Criar conta" onPress={handleSubmit} loading={isSubmitting} />

      <View style={{ marginTop: spacing.lg }}>
        <Button title="Já tenho conta" variant="ghost" onPress={() => navigation.navigate("Login")} />
      </View>
    </ScrollView>
  );
}
