import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";

import { checkHandleAvailability } from "../../api/auth";
import { Button } from "../../components/Button";
import { InfoDialog } from "../../components/InfoDialog";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

const HANDLE_PATTERN = /^[a-z0-9_]{3,30}$/;

export function RegisterScreen() {
  const { colors, type, spacing, shadow } = useTheme();
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
  const [erro, setErro] = useState<string | null>(null);

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
        : undefined;

  async function handleSubmit() {
    // Validação no cliente ANTES de bater no servidor: uma senha curta (a do
    // amigo tinha 6 caracteres) voltava como 422 e, antes, quebrava a tela.
    // Agora a pessoa recebe a mensagem certa na hora, sem nem enviar.
    const nome = displayName.trim();
    const emailN = email.trim().toLowerCase();
    if (!nome) {
      setErro("Digite seu nome de exibição.");
      return;
    }
    if (handleStatus !== "available") {
      setErro("Escolha um @handle válido e disponível (3-30 letras minúsculas, números ou _).");
      return;
    }
    if (!/^\S+@\S+\.\S+$/.test(emailN)) {
      setErro("Digite um e-mail válido (ex.: voce@email.com).");
      return;
    }
    if (password.length < 8) {
      setErro("A senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    setIsSubmitting(true);
    try {
      await signUp({ email: emailN, password, handle, display_name: nome });
    } catch (err: any) {
      setErro(mensagemDeErro(err, "Não foi possível criar sua conta. Tente novamente em instantes."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: spacing.lg }}>
        <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
          <View
            style={[
              {
                width: 60,
                height: 60,
                borderRadius: 20,
                backgroundColor: colors.primary,
                alignItems: "center",
                justifyContent: "center",
                marginBottom: spacing.sm,
              },
              shadow.md,
            ]}
          >
            <Ionicons name="fitness" size={32} color={colors.textOnPrimary} />
          </View>
          <Text style={[type.h1, { color: colors.textPrimary }]}>Criar conta</Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Leva menos de um minuto</Text>
        </View>

        <View
          style={[
            { backgroundColor: colors.surface, borderRadius: spacing.lg, padding: spacing.lg },
            shadow.sm,
          ]}
        >
          <TextField label="Nome de exibição" placeholder="Como quer ser chamado" value={displayName} onChangeText={setDisplayName} />
          <View>
            <TextField
              label="@handle (nome de usuário único)"
              autoCapitalize="none"
              placeholder="seu_handle"
              value={handle}
              onChangeText={(v) => setHandle(v.toLowerCase())}
              error={handleHint}
            />
            {handleStatus === "available" ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: -spacing.sm, marginBottom: spacing.sm, marginLeft: spacing.xs }}>
                <Ionicons name="checkmark-circle" size={14} color={colors.success} />
                <Text style={[type.caption, { color: colors.success }]}>Disponível!</Text>
              </View>
            ) : null}
          </View>
          <TextField
            label="E-mail"
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="voce@email.com"
            value={email}
            onChangeText={setEmail}
          />
          <TextField label="Senha" secureTextEntry placeholder="Mínimo 8 caracteres" value={password} onChangeText={setPassword} />

          <View style={{ marginTop: spacing.sm }}>
            <Button title="Criar conta" onPress={handleSubmit} loading={isSubmitting} />
          </View>
        </View>

        <View style={{ flexDirection: "row", justifyContent: "center", marginTop: spacing.lg }}>
          <Text style={[type.body, { color: colors.textSecondary }]}>Já tem conta? </Text>
          <Text
            style={[type.body, { color: colors.primary, fontWeight: "700" }]}
            onPress={() => navigation.navigate("Login")}
          >
            Entrar
          </Text>
        </View>
      </ScrollView>

      <InfoDialog
        visible={erro !== null}
        onClose={() => setErro(null)}
        title="Não foi possível criar sua conta"
        message={erro ?? undefined}
      />
    </KeyboardAvoidingView>
  );
}
