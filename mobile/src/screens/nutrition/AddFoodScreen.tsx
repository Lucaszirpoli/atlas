import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import {
  addFavoriteFood,
  createCustomFood,
  listFavoriteFoods,
  removeFavoriteFood,
  searchFoodBrands,
  searchFoods,
  type Food,
} from "../../api/foods";
import { createSavedMeal, listSavedMeals, logMeal, type SavedMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { QuantityEditor, type QuantityValue } from "../../components/QuantityEditor";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";
import { formatQuantity } from "../../utils/portion";
import { addRecentFood, listRecentFoods } from "../../utils/recentFoods";
import { mensagemDeErro } from "../../utils/errorMessage";

// Item da cesta: o alimento + como a quantidade foi escolhida (gramas ou
// medida caseira). unit_label/unit_amount nulos = registrado em gramas.
type CestaItem = { food: Food } & QuantityValue;

export function AddFoodScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId, barcodeResult } = route.params ?? {};
  const { user } = useAuth();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Food[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isSearchingBrands, setIsSearchingBrands] = useState(false);
  const [selectedFood, setSelectedFood] = useState<Food | null>(null);
  // Quantidade do fluxo de 1 alimento (código de barras / cadastro): gramas ou
  // medida caseira. A cesta guarda o dela por item.
  const [detailQty, setDetailQty] = useState<QuantityValue>({
    quantity_g: 100,
    unit_label: null,
    unit_amount: null,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Cadastro rápido de alimento que não existe na base (ataca o churn
  // "base de alimentos incompleta"). Valores por 100g.
  const [customMode, setCustomMode] = useState(false);
  const [custom, setCustom] = useState({ name: "", kcal: "", protein: "", carbs: "", fat: "" });
  const [isCreating, setIsCreating] = useState(false);

  // Favoritos: reuso em 1 toque, reduz a fricção do registro diário.
  const [favorites, setFavorites] = useState<Food[]>([]);
  const [favIds, setFavIds] = useState<Set<number>>(new Set());

  // CESTA (multi-seleção). Antes era um alimento por vez: pra registrar um pão
  // com ovo e queijo a pessoa fazia buscar→escolher→adicionar TRÊS vezes,
  // voltando à busca no meio. Agora marca os três e adiciona de uma vez.
  const [cesta, setCesta] = useState<CestaItem[]>([]);
  const [verCesta, setVerCesta] = useState(false);
  // Item da cesta cuja quantidade está sendo editada (abre o editor de medidas).
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const cestaIds = new Set(cesta.map((i) => i.food.id));

  // Últimos usados: atalho pra quem come quase sempre as mesmas coisas.
  const [recentes, setRecentes] = useState<Food[]>([]);
  // Receitas (SavedMeal). O backend e o cliente da API já existiam há tempos e
  // NENHUMA tela chamava — a pessoa não tinha como salvar "meu café da manhã".
  const [receitas, setReceitas] = useState<SavedMeal[]>([]);
  const [salvandoReceita, setSalvandoReceita] = useState(false);
  const [nomeReceita, setNomeReceita] = useState("");
  const [pedindoNome, setPedindoNome] = useState(false);
  const [aviso, setAviso] = useState<{ title: string; message: string } | null>(null);
  // "Criar receita": a cesta JÁ monta uma receita (marca ingredientes -> vê a
  // kcal total -> Salvar). Só faltava o convite visível pra esse fluxo.
  const [modoReceita, setModoReceita] = useState(false);

  function alternarNaCesta(food: Food) {
    setCesta((c) =>
      c.some((i) => i.food.id === food.id)
        ? c.filter((i) => i.food.id !== food.id)
        : [...c, { food, quantity_g: food.default_portion_g ?? 100, unit_label: null, unit_amount: null }]
    );
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
    if (cesta.length === 0) return;
    setIsSubmitting(true);
    try {
      // UMA chamada com todos os itens: o endpoint já aceita lista, era a tela
      // que mandava um por vez.
      await logMeal({
        meal_category_id: categoryId,
        logged_at: new Date().toISOString(),
        items: cesta.map((i) => ({
          food_id: i.food.id,
          quantity_g: i.quantity_g,
          unit_label: i.unit_label,
          unit_amount: i.unit_amount,
        })),
      });
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", mensagemDeErro(err, "Tente novamente."));
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
      message: `"${nome}" agora aparece aqui na busca — é só tocar pra usar de novo.`,
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
    listSavedMeals()
      .then(setReceitas)
      .catch(() => {});
  }, []);

  useEffect(() => {
    listFavoriteFoods()
      .then((f) => {
        setFavorites(f);
        setFavIds(new Set(f.map((x) => x.id)));
      })
      .catch(() => {});
  }, []);

  async function toggleFavorite(food: Food) {
    const isFav = favIds.has(food.id);
    setFavIds((prev) => {
      const next = new Set(prev);
      if (isFav) next.delete(food.id);
      else next.add(food.id);
      return next;
    });
    try {
      if (isFav) await removeFavoriteFood(food.id);
      else await addFavoriteFood(food.id);
    } catch {
      /* rollback: a gravação em si falhou, então desfaz a marcação otimista */
      const f = await listFavoriteFoods().catch(() => favorites);
      setFavorites(f);
      setFavIds(new Set(f.map((x) => x.id)));
      return;
    }
    // Recarregar a lista ficava DENTRO do try acima: falhando, o rollback
    // desmarcava o favorito na tela mesmo com ele já salvo no servidor — a tela
    // passava a mentir até a próxima abertura. Aqui é só atualização de vitrine.
    await listFavoriteFoods()
      .then(setFavorites)
      .catch(() => {});
  }

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
      setSelectedFood(food);
      setDetailQty({ quantity_g: food.default_portion_g ?? 100, unit_label: null, unit_amount: null });
    } catch (err: any) {
      Alert.alert("Não foi possível cadastrar", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setIsCreating(false);
    }
  }

  useEffect(() => {
    if (barcodeResult) {
      setSelectedFood(barcodeResult);
      setDetailQty({ quantity_g: barcodeResult.default_portion_g ?? 100, unit_label: null, unit_amount: null });
    }
  }, [barcodeResult]);

  // Busca em duas fases: (1) local sem acento, instantânea, aparece na hora;
  // (2) marcas do Open Food Facts (mais lenta, rede) encaixadas ao chegar,
  // sem duplicar o que já veio no local. `cancelled` evita que uma busca
  // antiga sobrescreva uma mais nova (race ao digitar rápido).
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
      // Fase 2: marcas ao vivo, encaixadas depois (sem bloquear a fase 1).
      setIsSearchingBrands(true);
      try {
        const brands = await searchFoodBrands(q);
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

  async function handleConfirm() {
    if (!selectedFood) return;
    const qty = detailQty.quantity_g;
    if (!qty || qty <= 0) {
      Alert.alert("Quantidade inválida", "Informe a quantidade.");
      return;
    }
    setIsSubmitting(true);
    try {
      // Só a gravação fica no try. O goBack() ficava aqui dentro e, se
      // falhasse, o catch acusava "não foi possível registrar" DEPOIS de a
      // refeição já estar salva — a pessoa via o erro, voltava, e o alimento
      // estava lá. Fora isso, o timeout curto do axios fazia o mesmo estrago
      // (ver REQUEST_TIMEOUT_MS em api/client.ts).
      await logMeal({
        meal_category_id: categoryId,
        logged_at: new Date().toISOString(),
        items: [
          {
            food_id: selectedFood.id,
            quantity_g: qty,
            unit_label: detailQty.unit_label,
            unit_amount: detailQty.unit_amount,
          },
        ],
      });
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", mensagemDeErro(err, "Tente novamente."));
      setIsSubmitting(false);
      return;
    }
    setIsSubmitting(false);
    navigation.goBack();
  }

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

  if (selectedFood) {
    const factor = (detailQty.quantity_g || 0) / 100;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.h1, { color: colors.textPrimary }]}>{selectedFood.name}</Text>
          {selectedFood.brand ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>
              {selectedFood.brand}
            </Text>
          ) : null}

          {/* GRAMAS **ou** MEDIDA CASEIRA (unidade, fatia, colher...), com opção
              de criar medida própria — a dor do "ovo em gramas é foda". */}
          <View style={{ marginTop: spacing.lg }}>
            <QuantityEditor food={selectedFood} value={detailQty} onChange={setDetailQty} />
          </View>
        </Card>

        <Card style={{ marginBottom: spacing.lg }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <NutrientPill label="kcal" value={Math.round(selectedFood.kcal_per_100g * factor)} color={colors.primary} />
            <NutrientPill label="prot" value={+(selectedFood.protein_g_per_100g * factor).toFixed(1)} color={colors.moduleTraining} />
            <NutrientPill label="carb" value={+(selectedFood.carbs_g_per_100g * factor).toFixed(1)} color={colors.info} />
            <NutrientPill label="gord" value={+(selectedFood.fat_g_per_100g * factor).toFixed(1)} color={colors.warning} />
          </View>
        </Card>

        <Button title="Adicionar à refeição" icon="✓" onPress={handleConfirm} loading={isSubmitting} />
        <View style={{ marginTop: spacing.sm }}>
          <Button title="Voltar à busca" variant="ghost" onPress={() => setSelectedFood(null)} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      {/* Busca */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderRadius: radius.pill,
          paddingHorizontal: spacing.md,
          height: 52,
          borderWidth: 1,
          borderColor: colors.border,
          marginBottom: spacing.md,
        }}
      >
        <Ionicons name="search" size={19} color={colors.textSecondary} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Buscar alimento ou marca..."
          placeholderTextColor={colors.textSecondary}
          style={[type.body, { flex: 1, color: colors.textPrimary, marginLeft: spacing.sm, height: "100%" }]}
        />
        {isSearching ? <ActivityIndicator size="small" color={colors.primary} /> : null}
      </View>

      {/* Ações rápidas */}
      {query.trim().length < 2 ? (
        <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
          <QuickAction
            icon="barcode"
            label="Código de barras"
            color={colors.primary}
            onPress={() => navigation.navigate("BarcodeScanner", { categoryId })}
          />
          <QuickAction
            icon="restaurant"
            label="Criar receita"
            color={colors.moduleTraining}
            onPress={() => setModoReceita(true)}
          />
          <QuickAction
            icon="camera"
            label={user?.plan === "pro" ? "Foto (IA)" : "Foto (Pro)"}
            color={colors.secondary}
            locked={user?.plan !== "pro"}
            onPress={() => {
              if (user?.plan !== "pro") {
                Alert.alert("Exclusivo do Pro", "Assine o Pro para registrar refeições por foto.");
                return;
              }
              navigation.navigate("MealPhoto", { categoryId });
            }}
          />
        </View>
      ) : null}

      {/* Convite do modo receita: explica o gesto (marcar ingredientes) que a
          cesta + "Salvar receita" já executam. */}
      {modoReceita ? (
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: spacing.sm,
            backgroundColor: colors.moduleTraining + "1E",
            borderRadius: radius.button,
            padding: spacing.md,
            marginBottom: spacing.md,
          }}
        >
          <Ionicons name="restaurant" size={20} color={colors.moduleTraining} />
          <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
            Busque e <Text style={{ fontWeight: "700" }}>marque cada ingrediente</Text> que você usou. A
            kcal total aparece embaixo — aí é só tocar em <Text style={{ fontWeight: "700" }}>Salvar receita</Text>.
          </Text>
          <TouchableOpacity onPress={() => setModoReceita(false)} hitSlop={8}>
            <Ionicons name="close" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>
      ) : null}

      <FlatList
        data={query.trim().length < 2 ? favorites : results}
        keyExtractor={(item) => String(item.id)}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={
          query.trim().length < 2 ? (
            <View>
              {/* Receitas salvas: um toque traz todos os itens de uma vez. */}
              {receitas.length > 0 ? (
                <>
                  <Secao titulo="🍽️ Suas receitas" />
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.md }}>
                    {receitas.map((r) => (
                      <Pressable
                        key={r.id}
                        onPress={() => usarReceita(r)}
                        style={{
                          backgroundColor: colors.surface,
                          borderWidth: 1,
                          borderColor: colors.border,
                          borderRadius: 999,
                          paddingVertical: 8,
                          paddingHorizontal: 13,
                        }}
                      >
                        <Text style={[type.caption, { color: colors.textPrimary }]}>
                          {r.name} · {r.items.length} itens
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                </>
              ) : null}

              {/* Últimos usados: quem come quase sempre o mesmo não deveria
                  digitar de novo. */}
              {recentes.length > 0 ? (
                <>
                  <Secao titulo="🕐 Últimos que você usou" />
                  <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.md }}>
                    {recentes.map((f) => {
                      const on = cestaIds.has(f.id);
                      return (
                        <Pressable
                          key={f.id}
                          onPress={() => alternarNaCesta(f)}
                          style={{
                            backgroundColor: on ? colors.primary : colors.surface,
                            borderWidth: 1,
                            borderColor: on ? colors.primary : colors.border,
                            borderRadius: 999,
                            paddingVertical: 8,
                            paddingHorizontal: 13,
                          }}
                        >
                          <Text style={[type.caption, { color: on ? colors.textOnPrimary : colors.textPrimary }]} numberOfLines={1}>
                            {f.name.length > 22 ? f.name.slice(0, 22) + "…" : f.name}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </>
              ) : null}

              {favorites.length > 0 ? <Secao titulo="⭐ Seus favoritos" /> : null}
            </View>
          ) : null
        }
        renderItem={({ item }) => {
          const marcado = cestaIds.has(item.id);
          return (
            <Pressable
              // Toque = marcar/desmarcar. O fluxo de um alimento só continua
              // igual (marca, "Adicionar" e pronto), mas agora dá pra marcar
              // pão, ovo e queijo e mandar os três de uma vez.
              onPress={() => alternarNaCesta(item)}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                backgroundColor: marcado ? colors.primarySoft ?? colors.surfaceAlt : colors.surface,
                borderRadius: radius.button,
                borderWidth: 1,
                borderColor: marcado ? colors.primary : "transparent",
                padding: spacing.md,
                marginBottom: spacing.sm,
                opacity: pressed ? 0.8 : 1,
              })}
            >
              <TouchableOpacity onPress={() => toggleFavorite(item)} hitSlop={8} style={{ marginRight: spacing.sm }}>
                <Ionicons
                  name={favIds.has(item.id) ? "star" : "star-outline"}
                  size={22}
                  color={favIds.has(item.id) ? colors.warning : colors.textSecondary}
                />
              </TouchableOpacity>
              <View style={{ flex: 1 }}>
                <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{item.name}</Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                  {item.brand ? `${item.brand} · ` : ""}
                  {Math.round(item.kcal_per_100g)} kcal/100g
                </Text>
              </View>
              <Ionicons
                name={marcado ? "checkmark-circle" : "add-circle-outline"}
                size={26}
                color={marcado ? colors.primary : colors.textSecondary}
              />
            </Pressable>
          );
        }}
        ListFooterComponent={
          query.trim().length >= 2 ? (
            <>
              {isSearchingBrands ? (
                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    paddingVertical: spacing.sm,
                  }}
                >
                  <ActivityIndicator size="small" color={colors.textSecondary} />
                  <Text style={[type.caption, { color: colors.textSecondary }]}>
                    Buscando marcas...
                  </Text>
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
                    marginTop: spacing.sm,
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

      {/* Barra da cesta: só aparece com algo marcado. É o que fecha o fluxo
          "marco pão, ovo e queijo e adiciono os três de uma vez". */}
      {cesta.length > 0 ? (
        <View
          style={{
            borderTopWidth: 1,
            borderTopColor: colors.border,
            backgroundColor: colors.surface,
            paddingTop: spacing.md,
            marginHorizontal: -spacing.lg,
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
          <View
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
              <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]} numberOfLines={2}>
                {emEdicao.food.name}
              </Text>
              <QuantityEditor
                food={emEdicao.food}
                value={{
                  quantity_g: emEdicao.quantity_g,
                  unit_label: emEdicao.unit_label,
                  unit_amount: emEdicao.unit_amount,
                }}
                onChange={(v) => atualizarItem(emEdicao.food.id, v)}
                compact
              />
              <View style={{ marginTop: spacing.lg }}>
                <Button title="Concluir" onPress={() => setEditandoId(null)} />
              </View>
            </Card>
          </View>
        );
      })()}

      <InfoDialog
        visible={aviso != null}
        onClose={() => setAviso(null)}
        title={aviso?.title ?? ""}
        message={aviso?.message}
      />

      {pedindoNome ? (
        <View
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
        </View>
      ) : null}
    </View>
  );
}

/** Cabeçalho de seção da busca (receitas / recentes / favoritos). */
function Secao({ titulo }: { titulo: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <Text
      style={[
        type.caption,
        { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" },
      ]}
    >
      {titulo}
    </Text>
  );
}

function QuickAction({
  icon,
  label,
  color,
  locked,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  color: string;
  locked?: boolean;
  onPress: () => void;
}) {
  const { colors, type, radius, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      style={{
        flex: 1,
        alignItems: "center",
        backgroundColor: colors.surface,
        borderRadius: radius.card,
        paddingVertical: spacing.md,
        borderWidth: 1,
        borderColor: colors.border,
        opacity: locked ? 0.65 : 1,
      }}
    >
      <View
        style={{
          width: 42,
          height: 42,
          borderRadius: 14,
          backgroundColor: color + "1E",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 6,
        }}
      >
        <Ionicons name={locked ? "lock-closed" : icon} size={20} color={color} />
      </View>
      <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "600" }]}>{label}</Text>
    </TouchableOpacity>
  );
}

function NutrientPill({ label, value, color }: { label: string; value: number; color: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ alignItems: "center", flex: 1 }}>
      <Text style={[type.h2, { color, fontSize: 20 }]}>{value}</Text>
      <Text style={[type.caption, { color: colors.textSecondary }]}>{label}</Text>
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
