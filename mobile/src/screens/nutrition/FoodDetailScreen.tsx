import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";

import {
  addFavoriteFood,
  listFavoriteFoods,
  removeFavoriteFood,
  type Food,
} from "../../api/foods";
import { logMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { UnitPicker } from "../../components/UnitPicker";
import type { QuantityValue } from "../../components/QuantityEditor";
import { useTheme } from "../../theme/ThemeProvider";
import { useMetaCalorica } from "../../utils/calorieTarget";
import { diaLabel, isoToday } from "../../utils/date";
import { mensagemDeErro } from "../../utils/errorMessage";
import {
  gramasBr,
  idrPercent,
  kcalParaKj,
  miligramasBr,
  numeroBr,
  por,
} from "../../utils/nutritionLabel";
import { formatQuantity, initialQuantityFor } from "../../utils/portion";
import { addRecentFood } from "../../utils/recentFoods";

/** Ficha do alimento: escolhe a quantidade, salva na refeição e mostra a
 * informação nutricional completa daquela porção (não por 100 g — o número que
 * interessa é o do que a pessoa vai comer). */
export function FoodDetailScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  // categoryId nunca falta: só se chega aqui pela busca (que veio do Diário,
  // sempre por uma refeição) ou pelo código de barras, que repassa o mesmo.
  const { food, categoryId, date } = route.params as {
    food: Food;
    categoryId: number;
    date?: string;
  };

  const metaKcal = useMetaCalorica();
  const [qty, setQty] = useState<QuantityValue>(() => initialQuantityFor(food));
  const [salvando, setSalvando] = useState(false);
  const [favorito, setFavorito] = useState(false);

  useEffect(() => {
    let vivo = true;
    listFavoriteFoods()
      .then((f) => vivo && setFavorito(f.some((x) => x.id === food.id)))
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [food.id]);

  async function alternarFavorito() {
    const alvo = !favorito;
    setFavorito(alvo);
    try {
      if (alvo) await addFavoriteFood(food.id);
      else await removeFavoriteFood(food.id);
    } catch {
      setFavorito(!alvo); // a gravação falhou: desfaz a marcação otimista
    }
  }

  const gramas = qty.quantity_g || 0;
  const kcal = ((food.kcal_per_100g || 0) * gramas) / 100;
  const prot = ((food.protein_g_per_100g || 0) * gramas) / 100;
  const carb = ((food.carbs_g_per_100g || 0) * gramas) / 100;
  const gord = ((food.fat_g_per_100g || 0) * gramas) / 100;

  function loggedAtFor(): string {
    if (!date) return new Date().toISOString();
    const agora = new Date();
    const [y, m, d] = String(date).split("-").map(Number);
    return new Date(y, m - 1, d, agora.getHours(), agora.getMinutes(), agora.getSeconds()).toISOString();
  }

  async function salvar() {
    if (!gramas || gramas <= 0) {
      Alert.alert("Quantidade inválida", "Informe a quantidade.");
      return;
    }
    setSalvando(true);
    try {
      await logMeal({
        meal_category_id: categoryId,
        logged_at: loggedAtFor(),
        items: [
          {
            food_id: food.id,
            quantity_g: gramas,
            unit_label: qty.unit_label,
            unit_amount: qty.unit_amount,
          },
        ],
      });
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", mensagemDeErro(err, "Tente novamente."));
      setSalvando(false);
      return;
    }
    await addRecentFood(food).catch(() => {});
    setSalvando(false);
    // Volta direto pro diário (e não pra busca): o registro terminou, e o
    // diário recarrega sozinho ao ganhar foco.
    navigation.navigate("Diary");
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ paddingBottom: spacing.xxl }}
      keyboardShouldPersistTaps="handled"
    >
      {/* Título */}
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md, flexDirection: "row", alignItems: "flex-start" }}>
        <View style={{ flex: 1 }}>
          <Text style={[type.h1, { color: colors.textPrimary, fontSize: 28, lineHeight: 34 }]}>
            {food.name}
          </Text>
          {food.brand ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>
              {food.brand}
            </Text>
          ) : null}
        </View>
        <Pressable onPress={alternarFavorito} hitSlop={10} style={{ paddingTop: 4, paddingLeft: spacing.sm }}>
          <Ionicons
            name={favorito ? "star" : "star-outline"}
            size={24}
            color={favorito ? colors.warning : colors.textSecondary}
          />
        </Pressable>
      </View>

      {/* Quantidade + unidade + salvar */}
      <View
        style={{
          backgroundColor: colors.surface,
          marginTop: spacing.md,
          paddingHorizontal: spacing.lg,
          paddingVertical: spacing.lg,
          borderTopWidth: 1,
          borderBottomWidth: 1,
          borderColor: colors.border,
        }}
      >
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
          Adicionar ao meu diário
          {date && date !== isoToday() ? ` · ${diaLabel(date).toLowerCase()}` : ""}
        </Text>

        <UnitPicker food={food} value={qty} onChange={setQty} />

        <View style={{ marginTop: spacing.lg }}>
          <Button title="SALVAR" onPress={salvar} loading={salvando} />
        </View>
      </View>

      {/* Resumo dos macros da porção escolhida — 2×2, como o rótulo. */}
      <View style={{ flexDirection: "row", borderBottomWidth: 1, borderColor: colors.border }}>
        <CelulaMacro
          rotulo="Calorias"
          valor={`${Math.round(kcal)} (${idrPercent(kcal, metaKcal)}%)`}
          borda
        />
        <CelulaMacro rotulo="Gorduras" valor={gramasBr(gord)} />
      </View>
      <View style={{ flexDirection: "row", borderBottomWidth: 1, borderColor: colors.border }}>
        <CelulaMacro rotulo="Carb" valor={gramasBr(carb)} borda />
        <CelulaMacro rotulo="Proteínas" valor={gramasBr(prot)} />
      </View>

      {/* Informação nutricional */}
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.xl }}>
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 30, lineHeight: 36 }]}>
          Informação Nutricional
        </Text>

        <Linha
          rotulo="Quantidade"
          valor={formatQuantity(gramas, qty.unit_label, qty.unit_amount)}
          forte
          topo
        />
        <Faixa />
        <Text
          style={[
            type.h2,
            { color: colors.textPrimary, textAlign: "right", marginTop: spacing.md, marginBottom: spacing.sm },
          ]}
        >
          Por porção
        </Text>
        <Faixa />

        <Linha rotulo="Energia" valor={`${numeroBr(kcalParaKj(kcal), 0)} KJ`} forte topo />
        <Linha valor={`${Math.round(kcal)} kcal`} semSeparador />

        <Linha rotulo="Carboidratos" valor={gramasBr(carb)} forte />
        <Linha rotulo="Açúcares" valor={gramasBr(por(food.sugar_g_per_100g, gramas))} recuado />
        <Linha rotulo="Proteínas" valor={gramasBr(prot)} forte />
        <Linha rotulo="Gorduras" valor={gramasBr(gord)} />
        <Linha rotulo="Fibras" valor={gramasBr(por(food.fiber_g_per_100g, gramas), 1)} />
        <Linha rotulo="Sódio" valor={miligramasBr(por(food.sodium_mg_per_100g, gramas))} />

        <Faixa />
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.md }]}>
          O "%" das calorias é a fatia da sua meta diária ({numeroBr(metaKcal, 0)} kcal). Um traço (—)
          significa que essa informação não consta na fonte deste alimento.
        </Text>
      </View>
    </ScrollView>
  );
}

/** Uma das quatro células do resumo de macros. */
function CelulaMacro({ rotulo, valor, borda }: { rotulo: string; valor: string; borda?: boolean }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        paddingVertical: spacing.md,
        backgroundColor: colors.surface,
        borderRightWidth: borda ? 1 : 0,
        borderColor: colors.border,
      }}
    >
      <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{rotulo}</Text>
      <Text style={[type.h2, { color: colors.textPrimary, marginTop: 2 }]}>{valor}</Text>
    </View>
  );
}

/** Linha da tabela nutricional. `forte` = nutriente principal (negrito),
 * `recuado` = sub-item de outro nutriente (açúcares dentro dos carboidratos). */
function Linha({
  rotulo,
  valor,
  forte,
  recuado,
  topo,
  semSeparador,
}: {
  rotulo?: string;
  valor: string;
  forte?: boolean;
  recuado?: boolean;
  topo?: boolean;
  semSeparador?: boolean;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingVertical: spacing.sm + 2,
        paddingLeft: recuado ? spacing.md : 0,
        borderTopWidth: topo || semSeparador ? 0 : 1,
        borderTopColor: colors.border,
      }}
    >
      <Text style={[forte ? type.h2 : type.body, { color: colors.textPrimary }]}>{rotulo ?? ""}</Text>
      <Text
        style={[
          forte ? type.h2 : type.body,
          { color: forte ? colors.textPrimary : colors.textSecondary },
        ]}
      >
        {valor}
      </Text>
    </View>
  );
}

/** A barra cinza que separa os blocos da tabela (mesma do rótulo impresso). */
function Faixa() {
  const { colors, spacing } = useTheme();
  return (
    <View
      style={{
        height: 10,
        backgroundColor: colors.surfaceAlt,
        borderRadius: 2,
        marginTop: spacing.sm,
      }}
    />
  );
}
