import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import type { Food } from "../../api/foods";
import { logMeal, parseMeal, type ParsedMealItem } from "../../api/meals";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";

// Item já interpretado e editável na revisão (o usuário confirma antes de salvar).
type ReviewItem = {
  raw: string;
  food: Food | null;
  alternatives: Food[];
  grams: string;
  status: ParsedMealItem["status"];
  showAlts: boolean;
};

function kcalOf(food: Food | null, grams: number): number {
  if (!food || !grams) return 0;
  return Math.round((food.kcal_per_100g * grams) / 100);
}

export function QuickLogScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId } = route.params as { categoryId: number };

  const [text, setText] = useState("");
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);

  async function handleParse() {
    if (text.trim().length < 2) return;
    setParsing(true);
    try {
      const parsed = await parseMeal(text.trim());
      setItems(
        parsed.map((p) => ({
          raw: p.raw,
          food: p.food,
          alternatives: p.alternatives,
          grams: p.quantity_g != null ? String(p.quantity_g) : "",
          status: p.status,
          showAlts: false,
        }))
      );
    } catch (err: any) {
      setInfo({ title: "Não consegui interpretar", message: err?.response?.data?.detail ?? "Tente de novo." });
    } finally {
      setParsing(false);
    }
  }

  function updateItem(idx: number, patch: Partial<ReviewItem>) {
    setItems((prev) => (prev ? prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)) : prev));
  }
  function removeItem(idx: number) {
    setItems((prev) => (prev ? prev.filter((_, i) => i !== idx) : prev));
  }

  const validItems = (items ?? []).filter((it) => it.food && Number(it.grams) > 0);

  async function handleSave() {
    if (validItems.length === 0) return;
    setSaving(true);
    try {
      await logMeal({
        meal_category_id: categoryId,
        logged_at: new Date().toISOString(),
        items: validItems.map((it) => ({ food_id: (it.food as Food).id, quantity_g: Number(it.grams) })),
      });
      navigation.goBack();
    } catch (err: any) {
      setInfo({ title: "Não consegui registrar", message: err?.response?.data?.detail ?? "Tente de novo." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
    >
      <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
        Escreva (ou fale pelo microfone do teclado 🎙️) o que você comeu — pode listar vários de uma vez.
      </Text>

      <TextInput
        value={text}
        onChangeText={setText}
        placeholder="Ex: 30g de requeijão, 2 ovos e uma banana"
        placeholderTextColor={colors.textSecondary}
        multiline
        style={[
          type.body,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.md,
            minHeight: 84,
            textAlignVertical: "top",
          },
        ]}
      />

      <View style={{ marginTop: spacing.sm }}>
        <Button
          title={parsing ? "Interpretando..." : "Interpretar"}
          icon="sparkles-outline"
          onPress={handleParse}
          loading={parsing}
          disabled={text.trim().length < 2}
        />
      </View>

      {items != null ? (
        items.length === 0 ? (
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.lg, textAlign: "center" }]}>
            Não consegui identificar itens. Tente algo como "150g de arroz e 100g de frango".
          </Text>
        ) : (
          <View style={{ marginTop: spacing.lg }}>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
              Confira antes de registrar
            </Text>

            {items.map((it, idx) => {
              const notFound = !it.food;
              return (
                <Card key={idx} style={{ marginBottom: spacing.sm }}>
                  <View style={{ flexDirection: "row", alignItems: "center" }}>
                    <View style={{ flex: 1 }}>
                      {notFound ? (
                        <>
                          <Text style={[type.body, { color: colors.warning, fontWeight: "700" }]}>
                            Não encontrei "{it.raw}"
                          </Text>
                          <Text style={[type.caption, { color: colors.textSecondary }]}>
                            {it.status === "sem_alimento" ? "Faltou dizer qual alimento." : "Tente outro nome ou adicione manualmente."}
                          </Text>
                        </>
                      ) : (
                        <>
                          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]} numberOfLines={2}>
                            {(it.food as Food).name}
                          </Text>
                          <Text style={[type.caption, { color: colors.textSecondary }]}>
                            {kcalOf(it.food, Number(it.grams))} kcal
                            {it.status === "porcao_estimada" ? " · porção estimada, ajuste se quiser" : ""}
                          </Text>
                        </>
                      )}
                    </View>

                    {!notFound ? (
                      <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                        <TextInput
                          value={it.grams}
                          onChangeText={(v) => updateItem(idx, { grams: v.replace(/[^0-9.]/g, "") })}
                          keyboardType="decimal-pad"
                          style={[
                            type.body,
                            {
                              color: colors.textPrimary,
                              backgroundColor: colors.surfaceAlt,
                              borderRadius: radius.button,
                              width: 60,
                              height: 40,
                              textAlign: "center",
                            },
                          ]}
                        />
                        <Text style={[type.caption, { color: colors.textSecondary }]}>g</Text>
                      </View>
                    ) : null}

                    <TouchableOpacity onPress={() => removeItem(idx)} hitSlop={8} style={{ marginLeft: spacing.sm }}>
                      <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
                    </TouchableOpacity>
                  </View>

                  {/* Trocar alimento (alternativas da busca) */}
                  {!notFound && it.alternatives.length > 0 ? (
                    <>
                      <TouchableOpacity
                        onPress={() => updateItem(idx, { showAlts: !it.showAlts })}
                        style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.sm }}
                      >
                        <Text style={[type.caption, { color: colors.primary, fontWeight: "600" }]}>
                          {it.showAlts ? "Fechar" : "Não é esse? Trocar"}
                        </Text>
                        <Ionicons name={it.showAlts ? "chevron-up" : "chevron-down"} size={13} color={colors.primary} style={{ marginLeft: 3 }} />
                      </TouchableOpacity>
                      {it.showAlts ? (
                        <View style={{ marginTop: spacing.xs, gap: 4 }}>
                          {it.alternatives.map((alt) => (
                            <TouchableOpacity
                              key={alt.id}
                              onPress={() => updateItem(idx, { food: alt, showAlts: false })}
                              style={{ paddingVertical: 6 }}
                            >
                              <Text style={[type.bodySmall, { color: colors.textPrimary }]} numberOfLines={1}>
                                {alt.name}{" "}
                                <Text style={{ color: colors.textSecondary }}>· {Math.round(alt.kcal_per_100g)} kcal/100g</Text>
                              </Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                      ) : null}
                    </>
                  ) : null}
                </Card>
              );
            })}

            <Button
              title={validItems.length > 0 ? `Registrar ${validItems.length} ${validItems.length === 1 ? "item" : "itens"}` : "Nada válido para registrar"}
              onPress={handleSave}
              loading={saving}
              disabled={validItems.length === 0}
            />
          </View>
        )
      ) : null}

      {parsing ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} /> : null}

      <InfoDialog visible={info != null} onClose={() => setInfo(null)} title={info?.title ?? ""} message={info?.message} />
    </ScrollView>
  );
}
