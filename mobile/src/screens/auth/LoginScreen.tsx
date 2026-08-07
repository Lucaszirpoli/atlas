import { GoogleSignin, statusCodes } from "@react-native-google-signin/google-signin";
import { useNavigation } from "@react-navigation/native";
import * as AppleAuthentication from "expo-apple-authentication";
import React, { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ATLAS_SLOGAN, AtlasLogo } from "../../components/AtlasLogo";
import { Button } from "../../components/Button";
import { Checkbox } from "../../components/Checkbox";
import { GoogleHandleModal } from "../../components/GoogleHandleModal";
import { InfoDialog } from "../../components/InfoDialog";
import { TextField } from "../../components/TextField";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

GoogleSignin.configure({
  webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
  // Web + Android + iOS usam o MESMO cliente "Web" como audiência do
  // idToken — é o `GOOGLE_OAUTH_CLIENT_ID` que o backend valida em
  // social_auth.verify_google_id_token. O que autoriza CADA plataforma a
  // pedir esse token é o cliente próprio dela cadastrado no Google Cloud:
  // Android (pacote + SHA-1) não precisa de nada aqui; iOS precisa do
  // iosClientId abaixo (senão o SDK não sabe qual client usar no fluxo
  // nativo, mesmo com o iosUrlScheme já configurado no app.json).
  iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID,
  offlineAccess: false,
});

export function LoginScreen() {
  const { colors, type, spacing, shadow, isDark } = useTheme();
  const { signIn, signInWithGoogle, signInWithApple } = useAuth();
  const navigation = useNavigation<any>();
  const insets = useSafeAreaInsets();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Ligado por padrão: é o comportamento que o app sempre teve, e o que quase
  // todo mundo quer. A caixa existe pra quem entrou no aparelho de outra pessoa.
  const [manterConectado, setManterConectado] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [googleLoading, setGoogleLoading] = useState(false);
  // Guarda o idToken entre a tentativa que falhou por falta de @handle (só no
  // PRIMEIRO login com essa conta Google) e a confirmação do modal — sem
  // guardar, a pessoa teria que passar pela tela do Google de novo.
  const [googlePendente, setGooglePendente] = useState<{ idToken: string; nome: string } | null>(null);

  const [appleLoading, setAppleLoading] = useState(false);
  const [applePendente, setApplePendente] = useState<{ idToken: string; nome: string } | null>(null);

  async function handleSubmit() {
    const login = email.trim().toLowerCase();
    if (!login || !password) {
      setErro("Preencha e-mail (ou usuário) e senha para entrar.");
      return;
    }
    setIsSubmitting(true);
    try {
      await signIn(login, password, manterConectado);
    } catch (err: any) {
      // Alert.alert nativo (a "tela feia") -> InfoDialog com o visual do ATLAS.
      // mensagemDeErro garante que um 422 (detail em lista) nunca vire tela
      // branca: vira uma frase legível.
      setErro(mensagemDeErro(err, "E-mail/usuário ou senha incorretos. Confira e tente de novo."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleSignIn() {
    setGoogleLoading(true);
    try {
      await GoogleSignin.hasPlayServices();
      const resp = await GoogleSignin.signIn();
      if (resp.type !== "success") return; // pessoa cancelou — sem erro, sem ação
      const idToken = resp.data.idToken;
      if (!idToken) {
        setErro("O Google não devolveu um token válido. Tente novamente.");
        return;
      }
      try {
        // Tenta como LOGIN (conta que já existe). Se for a primeira vez com
        // essa conta Google, o backend recusa (422) pedindo @handle — é o
        // catch abaixo que abre o modal pra completar o cadastro.
        await signInWithGoogle(idToken, undefined, manterConectado);
      } catch (err: any) {
        if (err?.response?.status === 422) {
          setGooglePendente({ idToken, nome: resp.data.user.name ?? resp.data.user.email.split("@")[0] });
          return;
        }
        throw err;
      }
    } catch (err: any) {
      if (err?.code === statusCodes.SIGN_IN_CANCELLED) return;
      setErro(mensagemDeErro(err, "Não foi possível entrar com o Google. Tente novamente."));
    } finally {
      setGoogleLoading(false);
    }
  }

  async function confirmarHandleGoogle(handle: string, displayName: string) {
    if (!googlePendente) return;
    setGoogleLoading(true);
    try {
      await signInWithGoogle(googlePendente.idToken, { handle, displayName }, manterConectado);
      setGooglePendente(null);
    } catch (err: any) {
      setErro(mensagemDeErro(err, "Não foi possível concluir seu cadastro com o Google."));
    } finally {
      setGoogleLoading(false);
    }
  }

  async function handleAppleSignIn() {
    if (appleLoading) return;
    setAppleLoading(true);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      const idToken = credential.identityToken;
      if (!idToken) {
        setErro("A Apple não devolveu um token válido. Tente novamente.");
        return;
      }
      // A Apple só devolve o nome no PRIMEIRO login desta conta com o app —
      // se vier vazio, a pessoa digita o nome ela mesma no modal.
      const nome = [credential.fullName?.givenName, credential.fullName?.familyName]
        .filter(Boolean)
        .join(" ");
      try {
        await signInWithApple(idToken, undefined, manterConectado);
      } catch (err: any) {
        if (err?.response?.status === 422) {
          setApplePendente({ idToken, nome });
          return;
        }
        throw err;
      }
    } catch (err: any) {
      if (err?.code === "ERR_REQUEST_CANCELED") return; // pessoa cancelou
      setErro(mensagemDeErro(err, "Não foi possível entrar com a Apple. Tente novamente."));
    } finally {
      setAppleLoading(false);
    }
  }

  async function confirmarHandleApple(handle: string, displayName: string) {
    if (!applePendente) return;
    setAppleLoading(true);
    try {
      await signInWithApple(applePendente.idToken, { handle, displayName }, manterConectado);
      setApplePendente(null);
    } catch (err: any) {
      setErro(mensagemDeErro(err, "Não foi possível concluir seu cadastro com a Apple."));
    } finally {
      setAppleLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={{
          flexGrow: 1,
          justifyContent: "center",
          padding: spacing.lg,
          paddingBottom: spacing.lg + insets.bottom,
        }}
      >
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
          <Text
            style={[
              type.bodySmall,
              { color: colors.textSecondary, marginTop: 6, textAlign: "center", maxWidth: 300, lineHeight: 21 },
            ]}
          >
            {ATLAS_SLOGAN}
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

          <Checkbox
            checked={manterConectado}
            onChange={setManterConectado}
            label="Manter conectado neste aparelho"
          />

          <TouchableOpacity onPress={() => navigation.navigate("ForgotPassword")} style={{ alignSelf: "flex-end", marginBottom: spacing.sm }}>
            <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "600" }]}>Esqueceu sua senha?</Text>
          </TouchableOpacity>

          <View style={{ marginTop: spacing.sm }}>
            <Button title="Entrar" onPress={handleSubmit} loading={isSubmitting} disabled={googleLoading} />
          </View>

          <View style={{ flexDirection: "row", alignItems: "center", marginVertical: spacing.md }}>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
            <Text style={[type.caption, { color: colors.textSecondary, marginHorizontal: spacing.sm }]}>ou</Text>
            <View style={{ flex: 1, height: 1, backgroundColor: colors.border }} />
          </View>

          <Button
            title="Continuar com Google"
            variant="secondary"
            onPress={handleGoogleSignIn}
            loading={googleLoading}
            disabled={isSubmitting}
          />

          {Platform.OS === "ios" ? (
            <AppleAuthentication.AppleAuthenticationButton
              buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
              buttonStyle={
                isDark
                  ? AppleAuthentication.AppleAuthenticationButtonStyle.WHITE
                  : AppleAuthentication.AppleAuthenticationButtonStyle.BLACK
              }
              cornerRadius={12}
              style={{
                height: 48,
                marginTop: spacing.sm,
                opacity: isSubmitting || googleLoading || appleLoading ? 0.6 : 1,
              }}
              onPress={handleAppleSignIn}
            />
          ) : null}
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

      <GoogleHandleModal
        visible={googlePendente !== null}
        defaultName={googlePendente?.nome ?? ""}
        submitting={googleLoading}
        onCancel={() => setGooglePendente(null)}
        onConfirm={confirmarHandleGoogle}
      />

      <GoogleHandleModal
        visible={applePendente !== null}
        defaultName={applePendente?.nome ?? ""}
        submitting={appleLoading}
        subtitle="Escolha um @handle único pra sua conta — o resto a Apple já preencheu."
        onCancel={() => setApplePendente(null)}
        onConfirm={confirmarHandleApple}
      />
    </KeyboardAvoidingView>
  );
}
