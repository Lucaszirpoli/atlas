import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import {
  createFoodPortion,
  deleteFoodPortion,
  listFoodPortions,
  type Food,
  type FoodPortion,
} from "../api/foods";
import { useTheme } from "../theme/ThemeProvider";
import { gramasLegivel } from "../utils/portion";
import type { QuantityValue } from "./QuantityEditor";

/** "Gramas" é sempre a opção base e não é uma FoodPortion — id sentinela -1. */
const GRAMAS: FoodPortion = { id: -1, label: "g", grams: 1, is_custom: false };

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Quantidade + unidade no formato de rótulo: um campo pro número e uma lista
 * suspensa pra medida ("1" · "unidade"), em vez da fileira de chips. As gramas
 * seguem sendo a base do cálculo — a medida é só a forma humana de escolher.
 *
 * A lista abre EMPURRANDO o conteúdo de baixo, não flutuando por cima: card
 * com `overflow: "hidden"` recortaria uma lista posicionada em absolute, e
 * ancorar um Modal exigiria medir a posição do campo em tela — medida que
 * falha silenciosamente quando o nó ainda não tem layout, deixando o menu sem
 * abrir. Empurrar sempre funciona, nos dois lugares onde este seletor é usado. */
export function UnitPicker({
  food,
  value,
  onChange,
}: {
  food: Food;
  value: QuantityValue;
  onChange: (v: QuantityValue) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [portions, setPortions] = useState<FoodPortion[]>([]);
  const [aberto, setAberto] = useState(false);
  const [criando, setCriando] = useState(false);
  const [novoLabel, setNovoLabel] = useState("");
  const [novoGramas, setNovoGramas] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let vivo = true;
    listFoodPortions(food.id)
      .then((p) => vivo && setPortions(p))
      .catch(() => vivo && setPortions([]));
    return () => {
      vivo = false;
    };
  }, [food.id]);

  const emGramas = value.unit_label == null;
  const unidade = emGramas ? GRAMAS : portions.find((p) => p.label === value.unit_label) ?? GRAMAS;
  // O número no campo: gramas (modo gramas) ou nº de unidades (modo medida).
  const amount = emGramas ? value.quantity_g : value.unit_amount ?? 1;
  const opcoes: FoodPortion[] = [...portions, GRAMAS];

  function selecionarUnidade(u: FoodPortion) {
    if (u.id === GRAMAS.id) {
      // Vindo de uma medida, cai nas gramas equivalentes (2 fatias -> 50 g) em
      // vez de zerar: a pessoa quer ajustar o peso, não recomeçar.
      onChange({ quantity_g: round1(value.quantity_g || 100), unit_label: null, unit_amount: null });
    } else {
      const a = emGramas ? 1 : value.unit_amount ?? 1;
      onChange({ quantity_g: round1(a * u.grams), unit_label: u.label, unit_amount: a });
    }
    setAberto(false);
    setCriando(false);
  }

  function mudarAmount(raw: string) {
    const n = Number(raw.replace(",", "."));
    const a = Number.isFinite(n) ? n : 0;
    if (emGramas) {
      onChange({ quantity_g: a, unit_label: null, unit_amount: null });
    } else {
      onChange({ quantity_g: round1(a * unidade.grams), unit_label: unidade.label, unit_amount: a });
    }
  }

  async function salvarNovaMedida() {
    const label = novoLabel.trim();
    const g = Number(novoGramas.replace(",", "."));
    if (!label || !Number.isFinite(g) || g <= 0) return;
    setSalvando(true);
    try {
      const nova = await createFoodPortion(food.id, { label, grams: g });
      setPortions(await listFoodPortions(food.id));
      setNovoLabel("");
      setNovoGramas("");
      selecionarUnidade(nova);
    } catch {
      // silencioso — gramas e as medidas existentes continuam funcionando
    } finally {
      setSalvando(false);
    }
  }

  async function apagarMedida(u: FoodPortion) {
    try {
      await deleteFoodPortion(food.id, u.id);
    } catch {
      return;
    }
    setPortions((ps) => ps.filter((p) => p.id !== u.id));
    if (value.unit_label === u.label) selecionarUnidade(GRAMAS);
  }

  const rotuloUnidade =
    unidade.id === GRAMAS.id ? "g" : `${unidade.label} (${gramasLegivel(unidade.grams)} g)`;

  const campoStyle = {
    flex: 1,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.button,
    height: 52,
    paddingHorizontal: spacing.md,
    justifyContent: "center" as const,
  };

  return (
    <View>
      {/* Quantidade */}
      <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
        <ColunaIcone nome="swap-vertical" />
        <View style={campoStyle}>
          <TextInput
            value={amount ? String(amount).replace(".", ",") : ""}
            onChangeText={(v) => mudarAmount(v.replace(/[^0-9.,]/g, ""))}
            keyboardType="decimal-pad"
            placeholder="0"
            placeholderTextColor={colors.textSecondary}
            style={[type.body, { color: colors.textPrimary, padding: 0 }]}
          />
        </View>
      </View>

      {/* Unidade */}
      <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm }}>
        <ColunaIcone nome="list" />
        <Pressable
          onPress={() => {
            setAberto((a) => !a);
            setCriando(false);
          }}
          style={({ pressed }) => [
            campoStyle,
            {
              flexDirection: "row",
              alignItems: "center",
              opacity: pressed ? 0.7 : 1,
              borderColor: aberto ? colors.primary : colors.border,
            },
          ]}
        >
          <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]} numberOfLines={1}>
            {rotuloUnidade}
          </Text>
          <Ionicons name={aberto ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
        </Pressable>
      </View>

      {/* Lista de medidas */}
      {aberto ? (
        <View
          style={{
            marginTop: spacing.xs,
            marginLeft: 48,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            borderWidth: 1,
            borderColor: colors.border,
            overflow: "hidden",
          }}
        >
          {criando ? (
            <View style={{ padding: spacing.md }}>
              <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
                Nova medida pra "{food.name}" — quanto pesa 1?
              </Text>
              <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
                <TextInput
                  value={novoLabel}
                  onChangeText={setNovoLabel}
                  placeholder="fatia"
                  placeholderTextColor={colors.textSecondary}
                  autoFocus
                  style={[
                    type.body,
                    {
                      flex: 1.3,
                      color: colors.textPrimary,
                      backgroundColor: colors.surface,
                      borderRadius: 8,
                      paddingHorizontal: 10,
                      height: 44,
                    },
                  ]}
                />
                <TextInput
                  value={novoGramas}
                  onChangeText={(v) => setNovoGramas(v.replace(/[^0-9.,]/g, ""))}
                  placeholder="g"
                  placeholderTextColor={colors.textSecondary}
                  keyboardType="decimal-pad"
                  style={[
                    type.body,
                    {
                      flex: 0.8,
                      color: colors.textPrimary,
                      backgroundColor: colors.surface,
                      borderRadius: 8,
                      paddingHorizontal: 10,
                      height: 44,
                      textAlign: "center",
                    },
                  ]}
                />
                <Pressable
                  onPress={salvarNovaMedida}
                  disabled={salvando || !novoLabel.trim() || !novoGramas}
                  style={{
                    backgroundColor: colors.primary,
                    borderRadius: 8,
                    paddingHorizontal: 14,
                    height: 44,
                    alignItems: "center",
                    justifyContent: "center",
                    opacity: salvando || !novoLabel.trim() || !novoGramas ? 0.5 : 1,
                  }}
                >
                  <Ionicons name="checkmark" size={18} color={colors.textOnPrimary} />
                </Pressable>
              </View>
            </View>
          ) : (
            <ScrollView style={{ maxHeight: 260 }} keyboardShouldPersistTaps="handled" nestedScrollEnabled>
              {opcoes.map((u, i) => {
                const on = u.id === GRAMAS.id ? emGramas : value.unit_label === u.label;
                return (
                  <Pressable
                    key={u.id}
                    onPress={() => selecionarUnidade(u)}
                    onLongPress={u.is_custom ? () => apagarMedida(u) : undefined}
                    style={({ pressed }) => ({
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 6,
                      paddingHorizontal: spacing.md,
                      height: 50,
                      borderTopWidth: i === 0 ? 0 : 1,
                      borderTopColor: colors.border,
                      backgroundColor: pressed ? colors.surface : "transparent",
                    })}
                  >
                    <Text
                      style={[type.body, { color: on ? colors.primary : colors.textPrimary, flex: 1 }]}
                      numberOfLines={1}
                    >
                      {u.id === GRAMAS.id ? "g" : `${u.label} (${gramasLegivel(u.grams)} g)`}
                    </Text>
                    {u.is_custom ? <Ionicons name="person" size={12} color={colors.textSecondary} /> : null}
                    {on ? <Ionicons name="checkmark" size={18} color={colors.primary} /> : null}
                  </Pressable>
                );
              })}
              <Pressable
                onPress={() => setCriando(true)}
                style={({ pressed }) => ({
                  flexDirection: "row",
                  alignItems: "center",
                  gap: 6,
                  paddingHorizontal: spacing.md,
                  height: 50,
                  borderTopWidth: 1,
                  borderTopColor: colors.border,
                  backgroundColor: pressed ? colors.surface : "transparent",
                })}
              >
                <Ionicons name="add" size={16} color={colors.primary} />
                <Text style={[type.body, { color: colors.primary }]}>Criar medida</Text>
              </Pressable>
              {portions.some((p) => p.is_custom) ? (
                <Text
                  style={[
                    type.caption,
                    {
                      color: colors.textSecondary,
                      paddingHorizontal: spacing.md,
                      paddingVertical: spacing.sm,
                    },
                  ]}
                >
                  Segure uma medida sua pra apagar.
                </Text>
              ) : null}
            </ScrollView>
          )}
        </View>
      ) : null}

      {/* Equivalência em gramas — some no modo gramas, onde seria redundante. */}
      {!emGramas ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, marginLeft: 48 }]}>
          = {gramasLegivel(value.quantity_g)} g
        </Text>
      ) : null}
    </View>
  );
}

/** Coluna de ícone à esquerda do campo — diz o que aquela linha controla
 * (quantidade / unidade) sem gastar uma linha de rótulo. */
function ColunaIcone({ nome }: { nome: keyof typeof Ionicons.glyphMap }) {
  const { colors } = useTheme();
  return (
    <View style={{ width: 40, alignItems: "center" }}>
      <Ionicons name={nome} size={20} color={colors.textSecondary} />
    </View>
  );
}
