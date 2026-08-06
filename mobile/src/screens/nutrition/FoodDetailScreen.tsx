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
import { Button } from "../../components/Button";
import { voltarPara } from "../../navigation/voltarPara";
import { UnitPicker } from "../../components/UnitPicker";
import type { QuantityValue } from "../../components/QuantityEditor";
import { useTheme } from "../../theme/ThemeProvider";
import { useMetaCalorica } from "../../utils/calorieTarget";
import { diaLabel, isoToday } from "../../utils/date";
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

/** Ficha do alimento: escolhe a quantidade, MARCA o alimento pra refeição e
 * mostra a informação nutricional completa daquela porção (não por 100 g — o
 * número que interessa é o do que a pessoa vai comer).
 *
 * Quem registra de verdade é a tela de busca, com a cesta inteira. Aqui a
 * pessoa só decide "quanto" — ver `adicionarNaLista`. */
export function FoodDetailScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  // `date` só serve pro aviso de "registrando em outro dia": a refeição e o dia
  // continuam com a tela de busca, que é quem grava.
  const { food, date } = route.params as {
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

  /** ESTE BOTÃO NÃO REGISTRA — ele marca.
   *
   * Antes, salvar aqui gravava só ESTE alimento e ia embora pro diário. Quem
   * tinha marcado outros na lista de busca (o quadradinho de cada linha)
   * perdia todos eles em silêncio: a cesta ficava pra trás e a refeição
   * entrava com um item só. Agora a ficha faz o mesmo que o quadradinho —
   * marca o alimento com a quantidade escolhida e devolve a pessoa pra lista,
   * onde ela confirma tudo de uma vez. Um só caminho, um só lugar de confirmar.
   */
  function adicionarNaLista() {
    if (!gramas || gramas <= 0) {
      Alert.alert("Quantidade inválida", "Informe a quantidade.");
      return;
    }
    setSalvando(true);
    addRecentFood(food).catch(() => {});
    // `merge`: o popTo troca os parâmetros da tela de destino, e sem mesclar a
    // busca perderia `categoryId`/`date` — ou seja, a refeição e o dia em que
    // o registro vai cair.
    voltarPara(
      navigation,
      "AddFood",
      {
        itemDaFicha: {
          food,
          quantity_g: gramas,
          unit_label: qty.unit_label ?? null,
          unit_amount: qty.unit_amount ?? null,
        },
      },
      true
    );
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
          <Button title="ADICIONAR" onPress={adicionarNaLista} loading={salvando} />
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, textAlign: "center", lineHeight: 17 }]}>
            Volta pra busca com este alimento marcado. Dá pra marcar outros e registrar todos de uma vez.
          </Text>
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
