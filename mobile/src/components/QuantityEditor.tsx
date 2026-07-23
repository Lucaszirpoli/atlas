import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import {
  createFoodPortion,
  deleteFoodPortion,
  listFoodPortions,
  type Food,
  type FoodPortion,
} from "../api/foods";
import { useTheme } from "../theme/ThemeProvider";
import { gramasLegivel } from "../utils/portion";

export type QuantityValue = {
  quantity_g: number;
  unit_label: string | null;
  unit_amount: number | null;
};

// "Gramas" é sempre a opção base — não é uma FoodPortion (id sentinela -1).
const GRAMAS: FoodPortion = { id: -1, label: "gramas", grams: 1, is_custom: false };

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Editor de quantidade: gramas OU medida caseira (unidade, fatia, colher),
 * com criação de medida personalizada. As gramas seguem sendo a base do
 * cálculo — a unidade é só a forma de escolher. Controlado: informa o valor e
 * recebe onChange a cada ajuste. */
export function QuantityEditor({
  food,
  value,
  onChange,
  compact,
}: {
  food: Food;
  value: QuantityValue;
  onChange: (v: QuantityValue) => void;
  compact?: boolean;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [portions, setPortions] = useState<FoodPortion[]>([]);
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

  function selecionarUnidade(u: FoodPortion) {
    if (u.id === GRAMAS.id) {
      onChange({ quantity_g: round1(value.quantity_g), unit_label: null, unit_amount: null });
    } else {
      // Mantém a contagem ao trocar de unidade; ao vir das gramas, começa em 1.
      const a = emGramas ? 1 : value.unit_amount ?? 1;
      onChange({ quantity_g: round1(a * u.grams), unit_label: u.label, unit_amount: a });
    }
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
      const lista = await listFoodPortions(food.id);
      setPortions(lista);
      setCriando(false);
      setNovoLabel("");
      setNovoGramas("");
      selecionarUnidade(nova);
    } catch {
      // silencioso — a pessoa continua podendo usar gramas/medidas existentes
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

  const chips: FoodPortion[] = [GRAMAS, ...portions];
  const gramasResultantes = emGramas ? value.quantity_g : round1(amount * unidade.grams);

  return (
    <View>
      {/* Campo do número + rótulo do que ele significa */}
      <View style={{ flexDirection: "row", alignItems: "flex-end" }}>
        <TextInput
          value={amount ? String(amount).replace(".", ",") : ""}
          onChangeText={(v) => mudarAmount(v.replace(/[^0-9.,]/g, ""))}
          keyboardType="decimal-pad"
          placeholder="0"
          placeholderTextColor={colors.textSecondary}
          style={[
            compact ? type.h1 : type.display,
            {
              color: colors.primary,
              borderBottomWidth: 3,
              borderBottomColor: colors.primary,
              minWidth: compact ? 72 : 110,
              paddingVertical: 2,
              textAlign: "left",
            },
          ]}
        />
        <Text style={[type.h2, { color: colors.textSecondary, marginLeft: spacing.sm, marginBottom: 8 }]}>
          {emGramas ? "gramas" : amount === 1 ? unidade.label : pluralOuLabel(unidade.label, amount)}
        </Text>
      </View>

      {/* Equivalência em gramas quando registrando por unidade */}
      {!emGramas ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          = {gramasLegivel(gramasResultantes)} g
        </Text>
      ) : null}

      {/* Seletor de medida: Gramas + medidas do alimento + criar nova */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.md }}>
        {chips.map((u) => {
          const on = u.id === GRAMAS.id ? emGramas : value.unit_label === u.label;
          return (
            <Pressable
              key={u.id}
              onPress={() => selecionarUnidade(u)}
              onLongPress={u.is_custom ? () => apagarMedida(u) : undefined}
              style={{
                backgroundColor: on ? colors.primary : colors.surfaceAlt,
                borderWidth: 1,
                borderColor: on ? colors.primary : colors.border,
                borderRadius: 999,
                paddingVertical: 7,
                paddingHorizontal: 13,
                flexDirection: "row",
                alignItems: "center",
                gap: 5,
              }}
            >
              <Text style={[type.bodySmall, { color: on ? colors.textOnPrimary : colors.textPrimary }]}>
                {u.id === GRAMAS.id ? "Gramas" : `1 ${u.label} · ${gramasLegivel(u.grams)}g`}
              </Text>
              {u.is_custom ? (
                <Ionicons name="person" size={11} color={on ? colors.textOnPrimary : colors.textSecondary} />
              ) : null}
            </Pressable>
          );
        })}

        {!criando ? (
          <Pressable
            onPress={() => setCriando(true)}
            style={{
              backgroundColor: "transparent",
              borderWidth: 1,
              borderStyle: "dashed",
              borderColor: colors.primary + "88",
              borderRadius: 999,
              paddingVertical: 7,
              paddingHorizontal: 13,
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Ionicons name="add" size={14} color={colors.primary} />
            <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "600" }]}>medida</Text>
          </Pressable>
        ) : null}
      </View>

      {/* Formulário de nova medida personalizada */}
      {criando ? (
        <View
          style={{
            marginTop: spacing.sm,
            padding: spacing.sm,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
          }}
        >
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
            Nova medida pra "{food.name}" (ex: "fatia" pesa 30 g)
          </Text>
          <View style={{ flexDirection: "row", gap: spacing.sm, alignItems: "center" }}>
            <TextInput
              value={novoLabel}
              onChangeText={setNovoLabel}
              placeholder="nome (fatia)"
              placeholderTextColor={colors.textSecondary}
              style={[
                type.body,
                { flex: 1.3, color: colors.textPrimary, backgroundColor: colors.surface, borderRadius: 8, paddingHorizontal: 10, height: 42 },
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
                { flex: 0.7, color: colors.textPrimary, backgroundColor: colors.surface, borderRadius: 8, paddingHorizontal: 10, height: 42, textAlign: "center" },
              ]}
            />
            <Pressable
              onPress={salvarNovaMedida}
              disabled={salvando || !novoLabel.trim() || !novoGramas}
              style={{
                backgroundColor: colors.primary,
                borderRadius: 8,
                paddingHorizontal: 14,
                height: 42,
                alignItems: "center",
                justifyContent: "center",
                opacity: salvando || !novoLabel.trim() || !novoGramas ? 0.5 : 1,
              }}
            >
              <Ionicons name="checkmark" size={18} color={colors.textOnPrimary} />
            </Pressable>
            <Pressable onPress={() => setCriando(false)} hitSlop={8}>
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>
        </View>
      ) : null}

      {portions.some((p) => p.is_custom) ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
          Segure uma medida sua pra apagar.
        </Text>
      ) : null}
    </View>
  );
}

// Pluralização leve do rótulo ao lado do número (não usa o util pra evitar
// import circular de estilo; mesma regra do primeiro-substantivo).
function pluralOuLabel(label: string, amount: number): string {
  if (amount <= 1) return label;
  const [primeira, ...resto] = label.split(" ");
  let p = primeira;
  if (primeira.endsWith("s")) p = primeira;
  else if (primeira.endsWith("ão")) p = primeira.slice(0, -2) + "ões";
  else if (/[rz]$/.test(primeira)) p = primeira + "es";
  else p = primeira + "s";
  return [p, ...resto].join(" ");
}
