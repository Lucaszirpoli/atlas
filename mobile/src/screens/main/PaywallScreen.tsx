import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";
import type { PurchasesPackage } from "react-native-purchases";

import { getOffering, restorePro, subscribePro, type Offering } from "../../api/billing";
import { configurePurchases, getCurrentOffering, isNativePurchasesAvailable } from "../../api/purchases";
import { AtlasLogo } from "../../components/AtlasLogo";
import { Button } from "../../components/Button";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

export function PaywallScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user, refreshUser } = useAuth();

  const [offering, setOffering] = useState<Offering | null>(null);
  const [nativePackage, setNativePackage] = useState<PurchasesPackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    getOffering()
      .then(setOffering)
      .finally(() => setLoading(false));

    // configurePurchases() só roda AQUI agora, não mais em todo login (ver
    // AuthContext.tsx) — só quem abre a tela de assinatura toca no SDK nativo
    // do RevenueCat. try/catch: erro de módulo nativo não pode travar a tela.
    if (isNativePurchasesAvailable() && user) {
      try {
        configurePurchases(String(user.id));
        getCurrentOffering()
          .then((o) => setNativePackage(o?.monthly ?? o?.availablePackages[0] ?? null))
          .catch(() => {});
      } catch {
        // RevenueCat indisponível/mal configurado neste aparelho — a tela
        // segue mostrando o preço; só a compra nativa fica bloqueada.
      }
    }
  }, [user?.id]);

  async function handleSubscribe() {
    setSubscribing(true);
    try {
      // A COMPRA é a única coisa que pode falhar de um jeito que justifique
      // dizer "não deu certo". Tudo que vem depois (confirmar o plano) fica
      // FORA deste try de propósito: uma falha de rede ao reconsultar não pode
      // fazer o app dizer "não deu pra concluir" pra quem acabou de pagar —
      // o dinheiro saiu, e a pessoa tentaria comprar de novo.
      await subscribePro(nativePackage ?? undefined);
    } catch (err: any) {
      setDone(mensagemDeErro(err, "Não deu pra concluir agora. Tente de novo."));
      setSubscribing(false);
      return;
    }

    // Daqui pra baixo a compra JÁ ACONTECEU. O backend só vira Pro quando o
    // webhook do RevenueCat chega (1-3s), então reconsultamos algumas vezes.
    // Se nem isso funcionar, a mensagem é tranquilizadora, nunca de erro.
    let isPro = false;
    try {
      for (let i = 0; i < 6 && !isPro; i++) {
        const u = await refreshUser();
        isPro = u?.plan === "pro";
        if (!isPro) await new Promise((r) => setTimeout(r, 1500));
      }
    } catch {
      // Rede caiu conferindo. A compra continua válida — o webhook resolve.
    }
    setDone(
      isPro
        ? "Bem-vindo ao ATLAS Pro! Todos os recursos avançados estão liberados. 🎉"
        : "Compra recebida! O Pro é liberado em instantes — se ainda aparecer Free, reabra o app em um minuto."
    );
    setSubscribing(false);
  }

  async function handleRestore() {
    setRestoring(true);
    try {
      const result = await restorePro();
      await refreshUser();
      setDone(
        result.is_pro
          ? "Sua assinatura Pro foi restaurada! 🎉"
          : "Não encontramos nenhuma assinatura ativa nessa conta da loja."
      );
    } catch (err: any) {
      setDone(mensagemDeErro(err, "Não deu pra restaurar agora. Tente de novo."));
    } finally {
      setRestoring(false);
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  const testMode = offering ? !offering.provider_ready && offering.dev_mode : false;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }} showsVerticalScrollIndicator={false}>
        <View style={{ alignItems: "center", marginTop: spacing.md, marginBottom: spacing.lg }}>
          <AtlasLogo size={64} color={colors.primary} seam={colors.bg} />
          <Text style={[type.h1, { color: colors.textPrimary, fontSize: 28, marginTop: spacing.md, letterSpacing: 4, fontWeight: "800" }]}>
            ATLAS PRO
          </Text>
          <Text style={[type.body, { color: colors.textSecondary, textAlign: "center", marginTop: 4 }]}>
            Todo o app manual continua de graça.{"\n"}O Pro solta a inteligência.
          </Text>
        </View>

        <View
          style={{
            backgroundColor: colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.lg,
            marginBottom: spacing.lg,
          }}
        >
          {(offering?.benefits ?? []).map((b) => (
            <View key={b} style={{ flexDirection: "row", alignItems: "flex-start", marginBottom: spacing.md }}>
              <View
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: 12,
                  backgroundColor: colors.primarySoft,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.sm,
                  marginTop: 1,
                }}
              >
                <Ionicons name="checkmark" size={15} color={colors.primary} />
              </View>
              <Text style={[type.body, { color: colors.textPrimary, flex: 1, lineHeight: 22 }]}>{b}</Text>
            </View>
          ))}
        </View>

        <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
          {nativePackage ? (
            <Text style={[type.display, { color: colors.textPrimary, fontSize: 40, lineHeight: 44 }]}>
              {nativePackage.product.priceString}
              <Text style={[type.body, { color: colors.textSecondary }]}> / mês</Text>
            </Text>
          ) : (
            <Text style={[type.display, { color: colors.textPrimary, fontSize: 40, lineHeight: 44 }]}>
              R$ {offering?.price_brl.toFixed(2).replace(".", ",")}
              <Text style={[type.body, { color: colors.textSecondary }]}> / {offering?.period}</Text>
            </Text>
          )}
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>Cancele quando quiser.</Text>
        </View>

        <Button
          title={testMode ? "Ativar Pro (modo teste)" : "Assinar Pro"}
          onPress={handleSubscribe}
          loading={subscribing}
        />

        {testMode ? (
          <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 17 }]}>
            Pagamento ainda em configuração. Neste build, o botão libera o Pro em modo de teste (sem cobrança) pra você
            experimentar tudo. A cobrança real entra pela loja (Apple/Google) quando o app for publicado.
          </Text>
        ) : (
          <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.sm }]}>
            A assinatura é processada com segurança pela App Store / Google Play.
          </Text>
        )}

        {isNativePurchasesAvailable() ? (
          <TouchableOpacity onPress={handleRestore} disabled={restoring} style={{ alignItems: "center", marginTop: spacing.lg }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>
              {restoring ? "Restaurando..." : "Restaurar compras"}
            </Text>
          </TouchableOpacity>
        ) : null}
      </ScrollView>

      <InfoDialog
        visible={done !== null}
        onClose={() => {
          setDone(null);
          navigation.goBack();
        }}
        title="ATLAS Pro"
        message={done ?? undefined}
      />
    </View>
  );
}
