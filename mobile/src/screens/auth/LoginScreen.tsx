import { useNavigation } from "@react-navigation/native";
import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from "react-native";

import { AtlasLogo } from "../../components/AtlasLogo";
import { Button } from "../../components/Button";
import { InfoDialog } from "../../components/InfoDialog";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

export function LoginScreen() {
  const { colors, type, spacing, shadow } = useTheme();
  const { signIn } = useAuth();
  const navigation = useNavigation<any>();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function handleSubmit() {
    const login = email.trim().toLowerCase();
    if (!login || !password) {
      setErro("Preencha e-mail (ou usuário) e senha para entrar.");
      return;
    }
    setIsSubmitting(true);
    try {
      await signIn(login, password);
    } catch (err: any) {
      // Alert.alert nativo (a "tela feia") -> InfoDialog com o visual do ATLAS.
      // mensagemDeErro garante que um 422 (detail em lista) nunca vire tela
      // branca: vira uma frase legível.
      setErro(mensagemDeErro(err, "E-mail/usuário ou senha incorretos. Confira e tente de novo."));
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
        {/* Marca */}
        <View style={{ alignItems: "center", marginBottom: spacing.xl }}>
          <AtlasLogo size={78} color={colors.primary} seam={colors.bg} />
          <Text
            style={[
              type.h1,
              {
                color: colors.textPrimary,
                fontSize: 34,
                marginTop: spacing.md,
                letterSpacing: 8,
                fontWeight: "800",
              },
            ]}
          >
            ATLAS
          </Text>
          <Text style={[type.body, { color: colors.textSecondary, marginTop: 4 }]}>
            Treino, dieta e evolução num lugar só
          </Text>
        </View>

        <View
          style={[
            {
              backgroundColor: colors.surface,
              borderRadius: spacing.lg,
              padding: spacing.lg,
            },
            shadow.sm,
          ]}
        >
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]}>
            Bem-vindo de volta
          </Text>

          <TextField
            label="E-mail ou usuário"
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="voce@email.com ou @seuusuario"
            value={email}
            onChangeText={setEmail}
          />
          <TextField
            label="Senha"
            secureTextEntry
            placeholder="••••••••"
            value={password}
            onChangeText={setPassword}
          />

          <View style={{ marginTop: spacing.sm }}>
            <Button title="Entrar" onPress={handleSubmit} loading={isSubmitting} />
          </View>
        </View>

        <View style={{ flexDirection: "row", justifyContent: "center", marginTop: spacing.lg }}>
          <Text style={[type.body, { color: colors.textSecondary }]}>Ainda não tem conta? </Text>
          <Text
            style={[type.body, { color: colors.primary, fontWeight: "700" }]}
            onPress={() => navigation.navigate("Register")}
          >
            Criar conta
          </Text>
        </View>
      </ScrollView>

      <InfoDialog
        visible={erro !== null}
        onClose={() => setErro(null)}
        title="Não foi possível entrar"
        message={erro ?? undefined}
      />
    </KeyboardAvoidingView>
  );
}
