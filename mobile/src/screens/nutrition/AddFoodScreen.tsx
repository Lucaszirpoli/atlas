import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation, useRoute } from "@react-navigation/native";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import {
  createCustomFood,
  listFavoriteFoods,
  searchFoodBrands,
  searchFoods,
  type Food,
} from "../../api/foods";
import { createSavedMeal, listSavedMeals, logMeal, type SavedMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { UnitPicker } from "../../components/UnitPicker";
import type { QuantityValue } from "../../components/QuantityEditor";
import { useTheme } from "../../theme/ThemeProvider";
import { useMetaCalorica } from "../../utils/calorieTarget";
import { diaLabel, isoToday } from "../../utils/date";
import { mensagemDeErro } from "../../utils/errorMessage";
import { idrPercent, porcaoDeReferencia } from "../../utils/nutritionLabel";
import { formatQuantity, initialQuantityFor } from "../../utils/portion";
import { addRecentFood, listRecentFoods } from "../../utils/recentFoods";
import { semAcento } from "../../utils/text";

// Item da cesta: o alimento + como a quantidade foi escolhida (gramas ou
// medida caseira). unit_label/unit_amount nulos = registrado em gramas.
type CestaItem = { food: Food } & QuantityValue;

const ABAS = [
  { id: "favoritos", titulo: "Favoritos" },
  { id: "receitas", titulo: "Receitas" },
  { id: "alimento", titulo: "Alimento" },
  { id: "recentes", titulo: "Consumidos recentemente" },
] as const;

type AbaId = (typeof ABAS)[number]["id"];

/** Casa o termo digitado com o nome/marca, sem acento nem maiúscula — o mesmo
 * comportamento da busca do servidor, mas aplicado às listas locais
 * (favoritos, recentes, receitas). */
function filtrarLocal<T>(itens: T[], termo: string, texto: (i: T) => string): T[] {
  const q = semAcento(termo.trim());
  if (q.length < 1) return itens;
  return itens.filter((i) => semAcento(texto(i)).includes(q));
}

export function AddFoodScreen() {
  const { colors, type, spacing, radius, shadow } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId, barcodeResult, date, itemDaFicha } = route.params ?? {};
  const metaKcal = useMetaCalorica();

  // Quando chega de um dia passado (Diário › setinha de dia), registra NAQUELE
  // dia — mantendo a hora atual, só trocando a data, pra não bagunçar a ordem
  // das refeições no diário do dia.
  function loggedAtFor(): string {
    if (!date) return new Date().toISOString();
    const agora = new Date();
    const [y, m, d] = String(date).split("-").map(Number);
    return new Date(y, m - 1, d, agora.getHours(), agora.getMinutes(), agora.getSeconds()).toISOString();
  }

  // Trava síncrona de "já estou registrando" (ver registrarCesta).
  const registrando = React.useRef(false);

  const [aba, setAba] = useState<AbaId>("alimento");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Food[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSearchingBrands, setIsSearchingBrands] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Cadastro rápido de alimento que não existe na base (ataca o churn
  // "base de alimentos incompleta"). Valores por 100g.
  const [customMode, setCustomMode] = useState(false);
  const [custom, setCustom] = useState({ name: "", kcal: "", protein: "", carbs: "", fat: "" });
  const [isCreating, setIsCreating] = useState(false);

  const [favorites, setFavorites] = useState<Food[]>([]);

  // CESTA (multi-seleção). O quadradinho de cada linha marca o alimento; a
  // barra de baixo adiciona todos de uma vez. Pra registrar pão, ovo e queijo
  // a pessoa marca os três em vez de repetir buscar→abrir→adicionar.
  const [cesta, setCesta] = useState<CestaItem[]>([]);
  const [verCesta, setVerCesta] = useState(false);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const cestaIds = useMemo(() => new Set(cesta.map((i) => i.food.id)), [cesta]);

  const [recentes, setRecentes] = useState<Food[]>([]);
  const [receitas, setReceitas] = useState<SavedMeal[]>([]);
  const [salvandoReceita, setSalvandoReceita] = useState(false);
  const [nomeReceita, setNomeReceita] = useState("");
  const [pedindoNome, setPedindoNome] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);

  function alternarNaCesta(food: Food) {
    setCesta((c) =>
      c.some((i) => i.food.id === food.id)
        ? c.filter((i) => i.food.id !== food.id)
        : [...c, { food, ...initialQuantityFor(food) }]
    );
  }

  function abrirFicha(food: Food) {
    navigation.navigate("FoodDetail", { food, categoryId, date });
  }

  function atualizarItem(foodId: number, v: QuantityValue) {
    setCesta((c) => c.map((i) => (i.food.id === foodId ? { ...i, ...v } : i)));
  }

  const totalCesta = cesta.reduce(
    (acc, i) => {
      const f = i.quantity_g / 100;
      return {
        kcal: acc.kcal + i.food.kcal_per_100g * f,
        prot: acc.prot + i.food.protein_g_per_100g * f,
        carb: acc.carb + i.food.carbs_g_per_100g * f,
        gord: acc.gord + i.food.fat_g_per_100g * f,
      };
    },
    { kcal: 0, prot: 0, carb: 0, gord: 0 }
  );

  async function registrarCesta() {
    // Guarda de clique duplo com REF, não com o estado `isSubmitting`: o estado
    // só desabilita o botão no próximo render, e dois toques rápidos disparam
    // os dois antes disso — a refeição entrava duas vezes. O ref muda no mesmo
    // instante. (A outra metade da proteção é a chave de idempotência do POST,
    // que cobre o retry automático da rede.)
    if (cesta.length === 0 || registrando.current) return;
    registrando.current = true;
    setIsSubmitting(true);
    try {
      // UMA chamada com todos os itens: o endpoint já aceita lista.
      await logMeal({
        meal_category_id: categoryId,
        logged_at: loggedAtFor(),
        items: cesta.map((i) => ({
          food_id: i.food.id,
          quantity_g: i.quantity_g,
          unit_label: i.unit_label,
          unit_amount: i.unit_amount,
        })),
      });
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", mensagemDeErro(err, "Tente novamente."));
      // Libera o ref só no erro: quem deu certo já está saindo da tela, e
      // reabrir o botão ali seria convidar o registro em dobro.
      registrando.current = false;
      setIsSubmitting(false);
      return;
    }
    // Guardar os recentes é atalho: se falhar, não afeta o registro.
    await Promise.all(cesta.map((i) => addRecentFood(i.food))).catch(() => {});
    setIsSubmitting(false);
    navigation.goBack();
  }

  async function salvarComoReceita() {
    const nome = nomeReceita.trim();
    if (!nome || cesta.length === 0) return;
    setSalvandoReceita(true);
    try {
      await createSavedMeal({
        name: nome,
        items: cesta.map((i) => ({
          food_id: i.food.id,
          quantity_g: i.quantity_g,
          unit_label: i.unit_label,
          unit_amount: i.unit_amount,
        })),
      });
    } catch (err: any) {
      setAviso({
        title: "Não consegui salvar a receita",
        message: mensagemDeErro(err, "Tente novamente."),
      });
      setSalvandoReceita(false);
      return;
    }
    setSalvandoReceita(false);
    setPedindoNome(false);
    setNomeReceita("");
    listSavedMeals().then(setReceitas).catch(() => {});
    setAviso({
      title: "Receita salva!",
      message: `"${nome}" agora aparece na aba Receitas — é só tocar pra usar de novo.`,
    });
  }

  /** Joga todos os itens da receita na cesta, já com as quantidades salvas. */
  function usarReceita(r: SavedMeal) {
    setCesta((c) => {
      const jaTem = new Set(c.map((i) => i.food.id));
      const novos: CestaItem[] = r.items
        .filter((i) => !jaTem.has(i.food_id))
        .map((i) => ({
          food: i.food,
          quantity_g: i.quantity_g,
          unit_label: i.unit_label,
          unit_amount: i.unit_amount,
        }));
      return [...c, ...novos];
    });
    setVerCesta(true);
  }

  useEffect(() => {
    listRecentFoods().then(setRecentes);
    listSavedMeals().then(setReceitas).catch(() => {});
  }, []);

  // Recarrega ao voltar da ficha: lá dá pra favoritar, e o alimento aberto
  // entra nos recentes ao ser salvo.
  useFocusEffect(
    useCallback(() => {
      listFavoriteFoods().then(setFavorites).catch(() => {});
      listRecentFoods().then(setRecentes);
    }, [])
  );

  function openCustom() {
    setCustom({ name: query.trim(), kcal: "", protein: "", carbs: "", fat: "" });
    setCustomMode(true);
  }

  async function handleCreateCustom() {
    const kcal = Number(custom.kcal.replace(",", "."));
    if (!custom.name.trim() || Number.isNaN(kcal) || kcal <= 0) {
      Alert.alert("Faltam dados", "Informe pelo menos o nome e as calorias por 100g.");
      return;
    }
    setIsCreating(true);
    try {
      const food = await createCustomFood({
        name: custom.name.trim(),
        kcal_per_100g: kcal,
        protein_g_per_100g: Number(custom.protein.replace(",", ".")) || 0,
        carbs_g_per_100g: Number(custom.carbs.replace(",", ".")) || 0,
        fat_g_per_100g: Number(custom.fat.replace(",", ".")) || 0,
      });
      setCustomMode(false);
      abrirFicha(food);
    } catch (err: any) {
      Alert.alert("Não foi possível cadastrar", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setIsCreating(false);
    }
  }

  // Produto lido no código de barras cai direto na ficha. Limpa o parâmetro
  // antes de navegar: senão ele fica pendurado na rota e reabriria a ficha
  // sozinho se esta tela remontasse.
  useEffect(() => {
    if (!barcodeResult) return;
    navigation.setParams({ barcodeResult: undefined });
    abrirFicha(barcodeResult);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [barcodeResult]);

  // Volta da ficha do alimento: ela não registra mais nada sozinha, só devolve
  // o alimento com a quantidade escolhida pra ENTRAR NA CESTA — do mesmo jeito
  // que o quadradinho da lista. Assim marcar três alimentos e abrir a ficha do
  // quarto continua terminando numa refeição com os quatro; antes o registro
  // saía com um só e os marcados sumiam sem aviso.
  useEffect(() => {
    if (!itemDaFicha) return;
    navigation.setParams({ itemDaFicha: undefined });
    setCesta((c) => [
      ...c.filter((i) => i.food.id !== itemDaFicha.food.id),
      {
        food: itemDaFicha.food,
        quantity_g: itemDaFicha.quantity_g,
        unit_label: itemDaFicha.unit_label ?? null,
        unit_amount: itemDaFicha.unit_amount ?? null,
      },
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemDaFicha]);

  // Busca em duas fases: (1) local sem acento, instantânea, aparece na hora;
  // (2) marcas ao vivo no Open Food Facts (já prioriza o catálogo do Brasil —
  // ver services/open_food_facts.py), encaixadas ao chegar, sem duplicar o
  // que já veio no local. `cancelled` evita que uma busca antiga sobrescreva
  // uma mais nova (race ao digitar rápido).
  //
  // FatSecret ficou de fora da busca (a API saiu cara demais pro uso real) —
  // a integração continua pronta no backend (services/fatsecret.py), só não é
  // chamada daqui. Reativar é só voltar a incluir searchFoodFatSecret aqui.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setIsSearching(false);
      setIsSearchingBrands(false);
      return;
    }
    let cancelled = false;
    setIsSearching(true);
    const timeout = setTimeout(async () => {
      try {
        const local = await searchFoods(q);
        if (cancelled) return;
        setResults(local);
      } finally {
        if (!cancelled) setIsSearching(false);
      }
      setIsSearchingBrands(true);
      try {
        const brands = await searchFoodBrands(q).catch(() => [] as Food[]);
        if (cancelled) return;
        setResults((prev) => {
          const seen = new Set(prev.map((f) => f.id));
          return [...prev, ...brands.filter((b) => !seen.has(b.id))];
        });
      } catch {
        // silencioso — se as marcas falharem, o local já está na tela
      } finally {
        if (!cancelled) setIsSearchingBrands(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [query]);

  // Cada aba filtra a SUA lista pelo mesmo termo: na aba Alimento o servidor
  // busca na base inteira; nas outras o filtro é local, sobre o que a pessoa
  // já tem. Digitar não troca de aba — o que você vê é sempre a aba aberta.
  const alimentosDaAba: Food[] =
    aba === "alimento"
      ? results
      : aba === "favoritos"
        ? filtrarLocal(favorites, query, (f) => `${f.name} ${f.brand ?? ""}`)
        : aba === "recentes"
          ? filtrarLocal(recentes, query, (f) => `${f.name} ${f.brand ?? ""}`)
          : [];
  const receitasDaAba = aba === "receitas" ? filtrarLocal(receitas, query, (r) => r.name) : [];

  if (customMode) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
            Cadastrar alimento
          </Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
            Valores por 100g (olhe a embalagem). Fica salvo pra você reusar depois.
          </Text>
          <CustomInput label="Nome" value={custom.name} onChangeText={(v) => setCustom((c) => ({ ...c, name: v }))} keyboard="default" />
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <CustomInput label="kcal" value={custom.kcal} onChangeText={(v) => setCustom((c) => ({ ...c, kcal: v }))} flex={1.2} />
            <CustomInput label="Prot (g)" value={custom.protein} onChangeText={(v) => setCustom((c) => ({ ...c, protein: v }))} />
            <CustomInput label="Carb (g)" value={custom.carbs} onChangeText={(v) => setCustom((c) => ({ ...c, carbs: v }))} />
            <CustomInput label="Gord (g)" value={custom.fat} onChangeText={(v) => setCustom((c) => ({ ...c, fat: v }))} />
          </View>
        </Card>
        <Button title="Cadastrar e usar" onPress={handleCreateCustom} loading={isCreating} />
        <View style={{ marginTop: spacing.sm }}>
          <Button title="Cancelar" variant="ghost" onPress={() => setCustomMode(false)} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Quando chega de um dia passado, deixa claro em qual dia vai
          registrar — senão parece que tá lançando em hoje por engano. */}
      {date && date !== isoToday() ? (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: colors.primary + "18",
            paddingVertical: 8,
            paddingHorizontal: spacing.lg,
          }}
        >
          <Ionicons name="calendar-outline" size={15} color={colors.primary} />
          <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>
            Registrando em {diaLabel(date).toLowerCase()}
          </Text>
        </View>
      ) : null}

      {/* Busca */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderRadius: radius.pill,
          paddingHorizontal: spacing.md,
          height: 48,
          borderWidth: 1,
          borderColor: colors.border,
          marginHorizontal: spacing.lg,
          marginTop: spacing.md,
        }}
      >
        <Ionicons name="search-outline" size={19} color={colors.textSecondary} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Buscar alimento ou marca..."
          placeholderTextColor={colors.textSecondary}
          style={[type.body, { flex: 1, color: colors.textPrimary, marginLeft: spacing.sm, height: "100%" }]}
        />
        {isSearching ? <ActivityIndicator size="small" color={colors.primary} /> : null}
        {query.length > 0 && !isSearching ? (
          <TouchableOpacity onPress={() => setQuery("")} hitSlop={10}>
            <Ionicons name="close-circle" size={20} color={colors.textSecondary} />
          </TouchableOpacity>
        ) : null}
      </View>

      {/* Abas */}
      <View style={{ borderBottomWidth: 1, borderBottomColor: colors.border, marginTop: spacing.md }}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: spacing.lg }}>
          {ABAS.map((a) => {
            const on = aba === a.id;
            return (
              <Pressable
                key={a.id}
                onPress={() => setAba(a.id)}
                style={{
                  paddingVertical: spacing.sm + 2,
                  paddingHorizontal: spacing.md,
                  borderBottomWidth: 2,
                  borderBottomColor: on ? colors.primary : "transparent",
                }}
              >
                <Text
                  style={[
                    type.caption,
                    {
                      color: on ? colors.primary : colors.textSecondary,
                      fontWeight: "700",
                      letterSpacing: 0.6,
                      textTransform: "uppercase",
                    },
                  ]}
                >
                  {a.titulo}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>
      </View>

      {aba === "receitas" ? (
        <FlatList
          data={receitasDaAba}
          keyExtractor={(r) => String(r.id)}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: 96 }}
          ListEmptyComponent={
            <Vazio
              icone="restaurant-outline"
              texto={
                receitas.length === 0
                  ? "Marque vários alimentos na aba Alimento e toque em “Salvar receita” — eles viram um atalho só, tipo “meu café da manhã”."
                  : "Nenhuma receita com esse nome."
              }
            />
          }
          renderItem={({ item }) => (
            <Pressable
              onPress={() => usarReceita(item)}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: spacing.md,
                paddingHorizontal: spacing.lg,
                borderBottomWidth: 1,
                borderBottomColor: colors.border,
                backgroundColor: pressed ? colors.surface : "transparent",
              })}
            >
              <View style={{ flex: 1 }}>
                <Text style={[type.body, { color: colors.textPrimary }]}>{item.name}</Text>
                <Text style={[type.caption, { color: colors.primary, marginTop: 2 }]}>
                  {item.items.length} {item.items.length === 1 ? "item" : "itens"}
                </Text>
              </View>
              <Ionicons name="add-circle-outline" size={24} color={colors.textSecondary} />
            </Pressable>
          )}
        />
      ) : (
        <FlatList
          data={alimentosDaAba}
          keyExtractor={(item) => String(item.id)}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: 96 }}
          ListEmptyComponent={
            isSearching ? null : (
              <Vazio
                icone={
                  aba === "favoritos"
                    ? "star-outline"
                    : aba === "recentes"
                      ? "time-outline"
                      : "search-outline"
                }
                texto={
                  aba === "favoritos"
                    ? "Nada aqui ainda. Abra um alimento e toque na estrela pra ele ficar sempre à mão."
                    : aba === "recentes"
                      ? "Os alimentos que você registrar aparecem aqui pra repetir num toque."
                      : query.trim().length < 2
                        ? "Digite pelo menos 2 letras pra buscar."
                        : "Nenhum alimento encontrado."
                }
              />
            )
          }
          renderItem={({ item }) => (
            <LinhaAlimento
              food={item}
              metaKcal={metaKcal}
              marcado={cestaIds.has(item.id)}
              onAbrir={() => abrirFicha(item)}
              onMarcar={() => alternarNaCesta(item)}
            />
          )}
          ListFooterComponent={
            aba === "alimento" && query.trim().length >= 2 ? (
              <>
                {isSearchingBrands ? (
                  <View
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      paddingVertical: spacing.md,
                    }}
                  >
                    <ActivityIndicator size="small" color={colors.textSecondary} />
                    <Text style={[type.caption, { color: colors.textSecondary }]}>Buscando marcas...</Text>
                  </View>
                ) : null}
                {!isSearching && !isSearchingBrands ? (
                  <TouchableOpacity
                    onPress={openCustom}
                    activeOpacity={0.7}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      borderWidth: 2,
                      borderStyle: "dashed",
                      borderColor: colors.primary + "66",
                      borderRadius: radius.card,
                      paddingVertical: spacing.md,
                      margin: spacing.lg,
                    }}
                  >
                    <Ionicons name="add-circle" size={20} color={colors.primary} />
                    <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]} numberOfLines={1}>
                      Não achou? Cadastrar "{query.trim()}"
                    </Text>
                  </TouchableOpacity>
                ) : null}
              </>
            ) : null
          }
        />
      )}

      {/* Pílula flutuante: os atalhos de entrada que não passam por digitar. */}
      {cesta.length === 0 ? (
        <View
          style={{
            position: "absolute",
            bottom: spacing.lg,
            alignSelf: "center",
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.pill,
            borderWidth: 1,
            borderColor: colors.border,
            paddingHorizontal: spacing.sm,
            ...shadow.md,
          }}
        >
          <AcaoPilula
            icone="barcode-outline"
            rotulo="Código de barras"
            onPress={() => navigation.navigate("BarcodeScanner", { categoryId })}
          />
          <View style={{ width: 1, height: 26, backgroundColor: colors.border }} />
          <AcaoPilula icone="create-outline" rotulo="Cadastrar alimento" onPress={openCustom} />
        </View>
      ) : null}

      {/* Barra da cesta: só aparece com algo marcado. É o que fecha o fluxo
          "marco pão, ovo e queijo e adiciono os três de uma vez". */}
      {cesta.length > 0 ? (
        <View
          style={{
            borderTopWidth: 1,
            borderTopColor: colors.border,
            backgroundColor: colors.surface,
            paddingTop: spacing.md,
            paddingHorizontal: spacing.lg,
          }}
        >
          <Pressable onPress={() => setVerCesta((v) => !v)} style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
                {cesta.length} {cesta.length === 1 ? "item" : "itens"} · {Math.round(totalCesta.kcal)} kcal
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary }]}>
                P {totalCesta.prot.toFixed(0)}g · C {totalCesta.carb.toFixed(0)}g · G {totalCesta.gord.toFixed(0)}g
                {"  ·  "}toque pra ajustar
              </Text>
            </View>
            <Ionicons name={verCesta ? "chevron-down" : "chevron-up"} size={20} color={colors.textSecondary} />
          </Pressable>

          {verCesta ? (
            <View style={{ marginTop: spacing.sm, maxHeight: 190 }}>
              <FlatList
                data={cesta}
                keyExtractor={(i) => String(i.food.id)}
                renderItem={({ item }) => (
                  // Toque na linha abre o editor de medida (gramas OU unidade,
                  // com criar medida própria). A quantidade aparece já no formato
                  // escolhido — "2 fatias · 50 g" ou "150 g".
                  <Pressable
                    onPress={() => setEditandoId(item.food.id)}
                    style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary }]} numberOfLines={1}>
                        {item.food.name}
                      </Text>
                      <Text style={[type.caption, { color: colors.primary, marginTop: 1 }]}>
                        {formatQuantity(item.quantity_g, item.unit_label, item.unit_amount)}
                        {"   ·  ajustar"}
                      </Text>
                    </View>
                    <TouchableOpacity onPress={() => alternarNaCesta(item.food)} hitSlop={8} style={{ marginLeft: 8 }}>
                      <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                    </TouchableOpacity>
                  </Pressable>
                )}
              />
            </View>
          ) : null}

          <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm, marginBottom: spacing.md }}>
            <View style={{ flex: 1 }}>
              <Button
                title={`Adicionar ${cesta.length > 1 ? `os ${cesta.length}` : ""}`}
                compact
                onPress={registrarCesta}
                loading={isSubmitting}
              />
            </View>
            <View style={{ flex: 1 }}>
              {/* Salvar como receita: a cesta JÁ É o gesto de montar uma. */}
              <Button title="Salvar receita" variant="ghost" compact onPress={() => setPedindoNome(true)} />
            </View>
          </View>
        </View>
      ) : null}

      {/* Editor de quantidade de um item da cesta (gramas/unidades). */}
      {(() => {
        const emEdicao = cesta.find((i) => i.food.id === editandoId);
        if (!emEdicao) return null;
        return (
          <KeyboardAvoidingView
            behavior={Platform.OS === "ios" ? "padding" : undefined}
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 0,
              bottom: 0,
              backgroundColor: "rgba(0,0,0,0.55)",
              alignItems: "center",
              justifyContent: "center",
              padding: spacing.lg,
            }}
          >
            <Card style={{ width: "100%", overflow: "visible" }}>
              <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]} numberOfLines={2}>
                {emEdicao.food.name}
              </Text>
              <UnitPicker
                food={emEdicao.food}
                value={{
                  quantity_g: emEdicao.quantity_g,
                  unit_label: emEdicao.unit_label,
                  unit_amount: emEdicao.unit_amount,
                }}
                onChange={(v) => atualizarItem(emEdicao.food.id, v)}
              />
              <View style={{ marginTop: spacing.lg }}>
                <Button title="Concluir" onPress={() => setEditandoId(null)} />
              </View>
            </Card>
          </KeyboardAvoidingView>
        );
      })()}

      <InfoDialog
        visible={aviso != null}
        onClose={() => setAviso(null)}
        title={aviso?.title ?? ""}
        message={aviso?.message}
      />

      {pedindoNome ? (
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.55)",
            alignItems: "center",
            justifyContent: "center",
            padding: spacing.lg,
          }}
        >
          <Card style={{ width: "100%" }}>
            <Text style={[type.h2, { color: colors.textPrimary }]}>Salvar como receita</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md }]}>
              Os {cesta.length} itens viram um atalho só. Ex: "meu café da manhã".
            </Text>
            <TextInput
              value={nomeReceita}
              onChangeText={setNomeReceita}
              placeholder="Nome da receita"
              placeholderTextColor={colors.textSecondary}
              autoFocus
              style={[
                type.body,
                {
                  color: colors.textPrimary,
                  backgroundColor: colors.surfaceAlt,
                  borderRadius: radius.button,
                  paddingHorizontal: spacing.md,
                  height: 50,
                  marginBottom: spacing.md,
                },
              ]}
            />
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Button title="Salvar" compact onPress={salvarComoReceita} loading={salvandoReceita} disabled={!nomeReceita.trim()} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Cancelar" variant="ghost" compact onPress={() => setPedindoNome(false)} />
              </View>
            </View>
          </Card>
        </KeyboardAvoidingView>
      ) : null}
    </View>
  );
}

/** Linha de resultado: nome, a porção de referência com a kcal DAQUELA porção
 * (não por 100 g), e o quadradinho de marcar.
 *
 * Dois alvos de toque diferentes de propósito: o corpo da linha ABRE a ficha
 * (ver macros, mudar a quantidade); o quadradinho só MARCA, pra somar vários
 * alimentos e mandar todos de uma vez sem sair da lista. */
function LinhaAlimento({
  food,
  metaKcal,
  marcado,
  onAbrir,
  onMarcar,
}: {
  food: Food;
  metaKcal: number;
  marcado: boolean;
  onAbrir: () => void;
  onMarcar: () => void;
}) {
  const { colors, type, spacing } = useTheme();
  const { rotulo, gramas } = porcaoDeReferencia(food);
  const kcal = ((food.kcal_per_100g || 0) * gramas) / 100;

  return (
    <Pressable
      onPress={onAbrir}
      style={({ pressed }) => ({
        flexDirection: "row",
        alignItems: "center",
        paddingVertical: spacing.md,
        paddingHorizontal: spacing.lg,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
        backgroundColor: pressed ? colors.surface : "transparent",
      })}
    >
      <View style={{ flex: 1, paddingRight: spacing.md }}>
        <Text style={[type.body, { color: colors.textPrimary }]} numberOfLines={2}>
          {food.name}
          {food.brand ? <Text style={{ color: colors.textSecondary }}>{` (${food.brand})`}</Text> : null}
        </Text>
        <Text style={[type.caption, { marginTop: 3 }]} numberOfLines={1}>
          <Text style={{ color: colors.primary }}>{rotulo}</Text>
          <Text style={{ color: colors.textSecondary }}>
            {`   IDR ${idrPercent(kcal, metaKcal)}% · ${Math.round(kcal)} kcal`}
          </Text>
        </Text>
      </View>

      <Pressable onPress={onMarcar} hitSlop={12}>
        <View
          style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            borderWidth: 2,
            borderColor: marcado ? colors.primary : colors.border,
            backgroundColor: marcado ? colors.primary : "transparent",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {marcado ? <Ionicons name="checkmark" size={17} color={colors.textOnPrimary} /> : null}
        </View>
      </Pressable>
    </Pressable>
  );
}

function AcaoPilula({
  icone,
  rotulo,
  onPress,
}: {
  icone: keyof typeof Ionicons.glyphMap;
  rotulo: string;
  onPress: () => void;
}) {
  const { colors, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      accessibilityLabel={rotulo}
      activeOpacity={0.7}
      style={{ paddingHorizontal: spacing.lg, paddingVertical: spacing.md }}
    >
      <Ionicons name={icone} size={24} color={colors.primary} />
    </TouchableOpacity>
  );
}

function Vazio({ icone, texto }: { icone: keyof typeof Ionicons.glyphMap; texto: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ alignItems: "center", paddingHorizontal: spacing.xl, paddingTop: spacing.xxl }}>
      <Ionicons name={icone} size={34} color={colors.textSecondary} />
      <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.md }]}>
        {texto}
      </Text>
    </View>
  );
}

function CustomInput({
  label,
  value,
  onChangeText,
  keyboard = "decimal-pad",
  flex = 1,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  keyboard?: "decimal-pad" | "default";
  flex?: number;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flex, marginBottom: spacing.sm }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(keyboard === "decimal-pad" ? v.replace(/[^0-9.,]/g, "") : v)}
        keyboardType={keyboard === "decimal-pad" ? "decimal-pad" : "default"}
        style={[
          type.body,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            height: 48,
            paddingHorizontal: spacing.md,
            textAlign: keyboard === "decimal-pad" ? "center" : "left",
          },
        ]}
      />
    </View>
  );
}
