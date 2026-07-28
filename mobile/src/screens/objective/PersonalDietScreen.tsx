import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { applyPersonalDiet, getPersonalDiet, type PersonalDiet } from "../../api/objective";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { exportDietAsPdf } from "../../utils/pdfExport";

/**
 * "Ver dieta em PDF" da aba Objetivo (ajuste pós-v36): a dieta que o Coaching
 * montou PRA ESSA PESSOA, batendo a meta de calorias/macros e respeitando as
 * restrições do questionário — não uma dieta pronta genérica (essas continuam
 * só na aba Dieta, em "Dietas prontas").
 */
export function PersonalDietScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const insets = useSafeAreaInsets();

  const [diet, setDiet] = useState<PersonalDiet | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [baixando, setBaixando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [confirmarUso, setConfirmarUso] = useState(false);
  const [sucesso, setSucesso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      setDiet(await getPersonalDiet());
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui montar sua dieta agora."));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function baixar() {
    if (!diet || baixando) return;
    setBaixando(true);
    try {
      await exportDietAsPdf({
        name: diet.name,
        tagline: diet.tagline,
        meals: diet.meals.map((m) => ({
          category: m.category,
          items: m.items.map((i) => ({ food_name: i.food_name, quantity_g: i.quantity_g, kcal: i.kcal })),
        })),
        totals: diet.totals,
      });
    } finally {
      setBaixando(false);
    }
  }

  async function usarHoje() {
    setConfirmarUso(false);
    setAplicando(true);
    try {
      const r = await applyPersonalDiet();
      setSucesso(
        `Registrei sua dieta no diário de hoje — ${r.items_logged} alimentos, ${r.totals.kcal} kcal. ` +
          "Você pode ajustar ou remover qualquer item na aba Dieta."
      );
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui registrar agora."));
    } finally {
      setAplicando(false);
    }
  }

  if (carregando) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  if (!diet) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg, paddingTop: spacing.xl + insets.top }}>
        <Card>
          <Text style={[type.body, { color: colors.textPrimary }]}>
            {erro ?? "Não consegui montar sua dieta agora."}
          </Text>
          <View style={{ marginTop: spacing.md }}>
            <Button title="Tentar de novo" variant="secondary" compact onPress={carregar} />
          </View>
        </Card>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View
        style={{
          flexDirection: "row", alignItems: "center", gap: spacing.sm,
          padding: spacing.lg, paddingTop: spacing.lg + insets.top,
        }}
      >
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          hitSlop={8}
          style={{ width: 40, height: 40, borderRadius: 13, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" }}
        >
          <Ionicons name="arrow-back" size={20} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22 }]}>{diet.name}</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xxl + insets.bottom }} showsVerticalScrollIndicator={false}>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>{diet.tagline}</Text>

        <View
          style={{
            flexDirection: "row", justifyContent: "space-around",
            backgroundColor: colors.surface, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border,
            paddingVertical: spacing.md, marginBottom: spacing.md,
          }}
        >
          <Total label="kcal" value={`${diet.totals.kcal}`} colors={colors} type={type} />
          <Total label="proteína" value={`${Math.round(diet.totals.protein_g)}g`} colors={colors} type={type} />
          <Total label="carbo" value={`${Math.round(diet.totals.carbs_g)}g`} colors={colors} type={type} />
          <Total label="gordura" value={`${Math.round(diet.totals.fat_g)}g`} colors={colors} type={type} />
        </View>

        {diet.restrictions.length > 0 ? (
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: spacing.md }}>
            {diet.restrictions.map((r) => (
              <View key={r} style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 10 }}>
                <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>{r}</Text>
              </View>
            ))}
          </View>
        ) : null}

        {diet.meals.map((meal) => (
          <View key={meal.category} style={{ marginBottom: spacing.md }}>
            <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", marginBottom: spacing.xs }]}>
              {meal.category}
            </Text>
            {meal.items.map((it) => (
              <View key={it.food_id + it.food_name} style={{ flexDirection: "row", alignItems: "center", paddingVertical: 4 }}>
                <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]} numberOfLines={1}>
                  {it.food_name}
                  <Text style={{ color: colors.textSecondary }}> · {Math.round(it.quantity_g)}g</Text>
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>{Math.round(it.kcal)} kcal</Text>
              </View>
            ))}
          </View>
        ))}

        {erro ? (
          <Text style={[type.bodySmall, { color: colors.warning, textAlign: "center", marginBottom: spacing.sm }]}>{erro}</Text>
        ) : null}

        <TouchableOpacity
          onPress={baixar}
          disabled={baixando}
          style={{
            flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
            paddingVertical: 10, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border,
            marginBottom: spacing.sm,
          }}
        >
          {baixando ? (
            <ActivityIndicator size="small" color={colors.textSecondary} />
          ) : (
            <Ionicons name="download-outline" size={16} color={colors.textSecondary} />
          )}
          <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>Baixar PDF</Text>
        </TouchableOpacity>

        <Button title="Usar esta dieta hoje" onPress={() => setConfirmarUso(true)} loading={aplicando} />
        <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 17 }]}>
          Dieta gerada com base no seu questionário — ponto de partida, não substitui orientação de um nutricionista.
        </Text>
      </ScrollView>

      <ConfirmDialog
        visible={confirmarUso}
        onClose={() => setConfirmarUso(false)}
        title="Usar esta dieta hoje?"
        message={`Vou registrar as ${diet.meals.length} refeições (${diet.totals.kcal} kcal) no seu diário de hoje. Isso não apaga o que você já registrou — só adiciona.`}
        confirmLabel="Registrar"
        onConfirm={usarHoje}
      />
      <InfoDialog
        visible={sucesso !== null}
        onClose={() => {
          setSucesso(null);
          navigation.navigate("NutritionModule");
        }}
        title="Dieta registrada ✓"
        message={sucesso ?? undefined}
      />
    </View>
  );
}

function Total({ label, value, colors, type }: { label: string; value: string; colors: any; type: any }) {
  return (
    <View style={{ alignItems: "center" }}>
      <Text style={[type.h2, { color: colors.textPrimary }]}>{value}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>{label}</Text>
    </View>
  );
}
