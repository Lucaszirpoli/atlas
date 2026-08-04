import { useNavigation } from "@react-navigation/native";
import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { forgotPassword, resetPassword } from "../../api/auth";
import { ATLAS_SLOGAN, AtlasLogo } from "../../components/AtlasLogo";
import { Button } from "../../components/Button";
import { InfoDialog } from "../../components/InfoDialog";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

/** Dois passos numa tela só (não duas telas): pedir o código e usá-lo é uma
 * única tarefa contínua pra quem está fazendo, só que o e-mail demora uns
 * segundos pra chegar — não é dois destinos de navegação diferentes. */
export function ForgotPasswordScreen() {
  const { colors, type, spacing, shadow } = useTheme();
  const { signInWithToken } = useAuth();
  const navigation = useNavigation<any>();

  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmSenha, setConfirmSenha] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoEnviado, setAvisoEnviado] = useState(false);

  async function handlePedirCodigo() {
    const emailN = email.trim().toLowerCase();
    if (!/^\S+@\S+\.\S+$/.test(emailN)) {
      setErro("Digite um e-mail válido (ex.: voce@email.com).");
      return;
    }
    setSubmitting(true);
    try {
      await forgotPassword(emailN);
      setEmail(emailN);
      setStep("code");
      setAvisoEnviado(true);
    } catch (err: any) {
      // A resposta do backend é sempre genérica (nunca diz se o e-mail existe),
      // então um erro aqui só pode ser rede/servidor — não confirmação de conta.
      setErro(mensagemDeErro(err, "Não consegui enviar agora. Tente de novo em instantes."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRedefinir() {
    if (code.trim().length !== 6) {
      setErro("Digite o código de 6 dígitos que chegou no seu e-mail.");
      return;
    }
    if (novaSenha.length < 8) {
      setErro("A nova senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (novaSenha !== confirmSenha) {
      setErro("As duas senhas digitadas não são iguais.");
      return;
    }
    setSubmitting(true);
    try {
      const { access_token } = await resetPassword({ email, code: code.trim(), new_password: novaSenha });
      // A pessoa já entra logada — senha acabou de ser digitada duas vezes
      // (nova + confirmação), pedir pra digitar de novo pra logar seria a
      // terceira. O token do próprio reset já serve pra isso.
      await signInWithToken(access_token);
    } catch (err: any) {
      setErro(mensagemDeErro(err, "Código inválido ou expirado. Peça um novo."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.bg }} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center", padding: spacing.lg }}>
        <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
          <AtlasLogo size={52} color={colors.primary} seam={colors.bg} />
          <Text style={[type.h1, { color: colors.textPrimary, marginTop: spacing.sm }]}>
            {step === "email" ? "Esqueceu sua senha?" : "Criar nova senha"}
          </Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", maxWidth: 300, lineHeight: 21, marginTop: 4 }]}>
            {step === "email" ? ATLAS_SLOGAN : `Enviamos um código de 6 dígitos pra ${email}.`}
          </Text>
        </View>

        <View style={[{ backgroundColor: colors.surface, borderRadius: spacing.lg, padding: spacing.lg }, shadow.sm]}>
          {step === "email" ? (
            <>
              <TextField
                label="E-mail"
                autoCapitalize="none"
                keyboardType="email-address"
                placeholder="voce@email.com"
                value={email}
                onChangeText={setEmail}
              />
              <View style={{ marginTop: spacing.sm }}>
                <Button title="Enviar código" onPress={handlePedirCodigo} loading={submitting} />
              </View>
            </>
          ) : (
            <>
              <TextField
                label="Código de 6 dígitos"
                keyboardType="number-pad"
                maxLength={6}
                placeholder="000000"
                value={code}
                onChangeText={(v) => setCode(v.replace(/\D/g, ""))}
              />
              <TextField
                label="Nova senha"
                secureTextEntry
                placeholder="Mínimo 8 caracteres"
                value={novaSenha}
                onChangeText={setNovaSenha}
              />
              <TextField
                label="Confirme a nova senha"
                secureTextEntry
                placeholder="Repita a senha"
                value={confirmSenha}
                onChangeText={setConfirmSenha}
              />
              <View style={{ marginTop: spacing.sm }}>
                <Button title="Redefinir senha" onPress={handleRedefinir} loading={submitting} />
              </View>
              <TouchableOpacity
                onPress={() => {
                  setStep("email");
                  setCode("");
                }}
                disabled={submitting}
                style={{ marginTop: spacing.md, alignItems: "center" }}
              >
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Não recebeu? Pedir outro código</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        <View style={{ flexDirection: "row", justifyContent: "center", marginTop: spacing.lg }}>
          <Text
            style={[type.body, { color: colors.primary, fontWeight: "700" }]}
            onPress={() => navigation.navigate("Login")}
          >
            Voltar para entrar
          </Text>
        </View>
      </ScrollView>

      <InfoDialog visible={erro !== null} onClose={() => setErro(null)} title="Ops" message={erro ?? undefined} />
      <InfoDialog
        visible={avisoEnviado}
        onClose={() => setAvisoEnviado(false)}
        title="Código enviado"
        message={`Se ${email} tiver uma conta, um código chega em instantes. Confira também o spam.`}
      />
    </KeyboardAvoidingView>
  );
}
