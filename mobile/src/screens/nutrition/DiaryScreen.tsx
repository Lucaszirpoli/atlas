import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import {
  createSavedMeal,
  deleteMealLog,
  listMealCategories,
  listMealsForDay,
  updateMealItem,
  type MealCategory,
  type MealLog,
  type MealLogItem,
} from "../../api/meals";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { InfoDialog } from "../../components/InfoDialog";
import { QuantityEditor, type QuantityValue } from "../../components/QuantityEditor";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { formatQuantity } from "../../utils/portion";
import { DietCoachHeader } from "../coaching/CoachModuleHeader";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const CATEGORY_ICONS: [RegExp, keyof typeof Ionicons.glyphMap][] = [
  [/café|cafe/i, "cafe"],
  [/almoço|almoco/i, "restaurant"],
  [/jantar/i, "moon"],
  [/ceia/i, "moon-outline"],
  [/lanche/i, "nutrition"],
];

function categoryIcon(name: string): keyof typeof Ionicons.glyphMap {
  const match = CATEGORY_ICONS.find(([re]) => re.test(name));
  return match ? match[1] : "restaurant-outline";
}

export function DiaryScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [categories, setCategories] = useState<MealCategory[]>([]);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [goal, setGoal] = useState<CalorieGoal | null>(null);
  const [water, setWater] = useState<WaterSummary | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Refeições recolhidas por padrão (estilo FatSecret): abre/fecha a lista de
  // itens tocando na barra "N itens".
  const [openCats, setOpenCats] = useState<Set<number>>(new Set());
  // Item cuja quantidade está sendo corrigida (toque no alimento no diário).
  const [editing, setEditing] = useState<MealLogItem | null>(null);
  const [editQty, setEditQty] = useState<QuantityValue>({ quantity_g: 100, unit_label: null, unit_amount: null });
  const [savingEdit, setSavingEdit] = useState(false);
  // itemCount = quantos alimentos aquele registro tem. O backend só apaga a
  // REFEIÇÃO inteira (não item a item), então a confirmação precisa dizer isso
  // quando o registro tem mais de um alimento.
  const [deleteTarget, setDeleteTarget] = useState<
    { mealLogId: number; foodName: string; itemCount: number } | null
  >(null);
  // "Salvar o dia inteiro como dieta": junta tudo que foi comido hoje num
  // modelo reutilizável (um SavedMeal), que reaparece em "Suas receitas".
  const [savingDay, setSavingDay] = useState(false);
  const [dayAviso, setDayAviso] = useState<{ title: string; message: string } | null>(null);

  async function loadAll() {
    const [cats, mealsForDay, currentGoal, waterToday] = await Promise.all([
      listMealCategories(),
      listMealsForDay(todayIso()),
      getCurrentGoal(),
      getTodayWaterSummary(),
    ]);
    setCategories(cats);
    setMeals(mealsForDay);
    setGoal(currentGoal);
    setWater(waterToday);
  }

  function toggleCat(id: number) {
    setOpenCats((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openEditor(item: MealLogItem) {
    setEditQty({ quantity_g: item.quantity_g, unit_label: item.unit_label, unit_amount: item.unit_amount });
    setEditing(item);
  }

  async function salvarEdicao() {
    if (!editing) return;
    setSavingEdit(true);
    try {
      await updateMealItem(editing.id, {
        quantity_g: editQty.quantity_g,
        unit_label: editQty.unit_label,
        unit_amount: editQty.unit_amount,
      });
      setEditing(null);
      await loadAll();
    } catch {
      /* silencioso — mantém o modal aberto pra tentar de novo */
    } finally {
      setSavingEdit(false);
    }
  }

  // Água mora aqui junto com as calorias: é o lugar que a pessoa abre pra
  // anotar o que consumiu no dia.
  async function handleAddWater(ml: number) {
    setWater((prev) => (prev ? { ...prev, total_ml_today: prev.total_ml_today + ml } : prev));
    try {
      await logWater(ml);
    } finally {
      getTodayWaterSummary().then(setWater).catch(() => {});
    }
  }

  async function confirmDeleteFood() {
    if (!deleteTarget) return;
    await deleteMealLog(deleteTarget.mealLogId);
    setDeleteTarget(null);
    loadAll();
  }

  async function salvarDiaComoDieta() {
    const itens = meals.flatMap((m) => m.items).map((i) => ({ food_id: i.food_id, quantity_g: i.quantity_g }));
    if (itens.length === 0) return;
    const hoje = new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
    setSavingDay(true);
    try {
      await createSavedMeal({ name: `Dieta de ${hoje}`, items: itens });
      setDayAviso({
        title: "Dia salvo como dieta!",
        message: `Os ${itens.length} itens de hoje viraram o modelo "Dieta de ${hoje}" — reutilize em Adicionar alimento › Suas receitas.`,
      });
    } catch (err: any) {
      setDayAviso({ title: "Não consegui salvar", message: mensagemDeErro(err, "Tente novamente.") });
    } finally {
      setSavingDay(false);
    }
  }

  useFocusEffect(
    useCallback(() => {
      loadAll();
    }, [])
  );

  async function handleRefresh() {
    setIsRefreshing(true);
    try {
      await loadAll();
    } finally {
      setIsRefreshing(false);
    }
  }

  const allItems = meals.flatMap((m) => m.items);
  const consumed = {
    kcal: allItems.reduce((s, i) => s + i.kcal, 0),
    protein: allItems.reduce((s, i) => s + i.protein_g, 0),
    carbs: allItems.reduce((s, i) => s + i.carbs_g, 0),
    fat: allItems.reduce((s, i) => s + i.fat_g, 0),
  };
  const kcalGoal = goal?.kcal ?? 0;
  const restantes = Math.round(kcalGoal - consumed.kcal);
  const overGoal = kcalGoal > 0 && consumed.kcal > kcalGoal;
  const pct = kcalGoal > 0 ? Math.min(consumed.kcal / kcalGoal, 1) : 0;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />}
      showsVerticalScrollIndicator={false}
    >
      {/* Cabeçalho do coach (Pro): meta calórica + macros + leitura. Some no Free. */}
      <DietCoachHeader />

      {/* RESUMO COMPACTO — "restantes" em destaque + barra + macros. Toque abre a
          meta. Sem o anel grande de antes: as refeições são o foco. */}
      <Card style={{ marginBottom: spacing.md }}>
        <TouchableOpacity activeOpacity={0.85} onPress={() => navigation.navigate("GoalSettings")}>
          <View style={{ flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between" }}>
            <View>
              <Text style={[type.caption, { color: colors.textSecondary }]}>
                {kcalGoal > 0 ? (overGoal ? "Acima da meta" : "Restantes hoje") : "Consumido hoje"}
              </Text>
              <View style={{ flexDirection: "row", alignItems: "baseline", gap: 5 }}>
                <Text style={[type.display, { color: overGoal ? colors.warning : colors.textPrimary, fontSize: 34 }]}>
                  {kcalGoal > 0 ? Math.abs(restantes) : Math.round(consumed.kcal)}
                </Text>
                <Text style={[type.body, { color: colors.textSecondary }]}>kcal</Text>
              </View>
            </View>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
                {Math.round(consumed.kcal)}
                <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>
                  {kcalGoal > 0 ? ` / ${Math.round(kcalGoal)}` : ""}
                </Text>
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 3, marginTop: 2 }}>
                <Ionicons name="flag" size={12} color={colors.primary} />
                <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>
                  {kcalGoal > 0 ? "Minha meta" : "Definir meta"}
                </Text>
              </View>
            </View>
          </View>
          {kcalGoal > 0 ? (
            <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surfaceAlt, overflow: "hidden", marginTop: spacing.sm }}>
              <View style={{ width: `${pct * 100}%`, height: "100%", backgroundColor: overGoal ? colors.warning : colors.primary }} />
            </View>
          ) : null}
        </TouchableOpacity>

        {/* Macros em 3 barrinhas */}
        <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.md }}>
          <MacroBar label="Proteína" value={consumed.protein} goal={goal?.protein_g ?? 0} color={colors.moduleTraining} />
          <MacroBar label="Carbo" value={consumed.carbs} goal={goal?.carbs_g ?? 0} color={colors.info} />
          <MacroBar label="Gordura" value={consumed.fat} goal={goal?.fat_g ?? 0} color={colors.warning} />
        </View>

        {/* Ações do dia: histórico + salvar dia. */}
        <View
          style={{
            flexDirection: "row",
            marginTop: spacing.md,
            borderTopWidth: 1,
            borderTopColor: colors.border,
          }}
        >
          <TouchableOpacity
            onPress={() => navigation.navigate("CalorieHistory")}
            activeOpacity={0.7}
            style={{ flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, paddingVertical: spacing.sm, paddingBottom: 0 }}
          >
            <Ionicons name="stats-chart" size={16} color={colors.primary} />
            <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]}>Histórico</Text>
          </TouchableOpacity>
          {allItems.length > 0 ? (
            <TouchableOpacity
              onPress={salvarDiaComoDieta}
              disabled={savingDay}
              activeOpacity={0.7}
              style={{
                flex: 1,
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                paddingVertical: spacing.sm,
                paddingBottom: 0,
                borderLeftWidth: 1,
                borderLeftColor: colors.border,
                opacity: savingDay ? 0.5 : 1,
              }}
            >
              <Ionicons name="bookmark-outline" size={16} color={colors.moduleTraining} />
              <Text style={[type.bodySmall, { color: colors.moduleTraining, fontWeight: "700" }]}>Salvar dia</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </Card>

      {/* Água — compacta, logo abaixo do resumo. */}
      <Card style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
          <Ionicons name="water" size={18} color={colors.info} />
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16, flex: 1, marginLeft: spacing.xs }]}>
            Água
          </Text>
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
            {((water?.total_ml_today ?? 0) / 1000).toFixed(1)} L
            <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>
              {" "}
              / {((water?.goal_ml ?? 0) / 1000).toFixed(1)} L
            </Text>
          </Text>
        </View>
        <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surfaceAlt, overflow: "hidden" }}>
          <View
            style={{
              width: `${Math.min(((water?.total_ml_today ?? 0) / Math.max(water?.goal_ml ?? 1, 1)) * 100, 100)}%`,
              height: "100%",
              backgroundColor: colors.info,
            }}
          />
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
          {[200, 300, 500].map((ml) => (
            <TouchableOpacity
              key={ml}
              onPress={() => handleAddWater(ml)}
              activeOpacity={0.7}
              style={{
                flex: 1,
                alignItems: "center",
                backgroundColor: colors.info + "1A",
                borderRadius: radius.button,
                paddingVertical: spacing.sm,
              }}
            >
              <Text style={[type.bodySmall, { color: colors.info, fontWeight: "700" }]}>+{ml}ml</Text>
            </TouchableOpacity>
          ))}
        </View>
      </Card>

      {/* REFEIÇÕES — o foco da tela, estilo FatSecret. */}
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Refeições de hoje
      </Text>
      {categories.map((category) => {
        const categoryMeals = meals.filter((m) => m.meal_category_id === category.id);
        const categoryItems = categoryMeals.flatMap((m) => m.items.map((item) => ({ item, mealLogId: m.id })));
        const categoryKcal = categoryItems.reduce((s, x) => s + x.item.kcal, 0);
        const hasItems = categoryItems.length > 0;
        const isOpen = openCats.has(category.id);
        return (
          <Card key={category.id} padded={false} style={{ marginBottom: spacing.sm }}>
            {/* Cabeçalho: ícone + nome ....... kcal + botão "+" */}
            <View style={{ flexDirection: "row", alignItems: "center", padding: spacing.md, paddingBottom: hasItems ? spacing.sm : spacing.md }}>
              <View
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 13,
                  backgroundColor: colors.primarySoft,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.sm,
                }}
              >
                <Ionicons name={categoryIcon(category.name)} size={20} color={colors.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: colors.textPrimary, fontSize: 17 }]}>{category.name}</Text>
                {categoryKcal > 0 ? (
                  <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                    {Math.round(categoryKcal)} kcal
                  </Text>
                ) : null}
              </View>
              <TouchableOpacity
                onPress={() => navigation.navigate("AddFood", { categoryId: category.id })}
                activeOpacity={0.8}
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 19,
                  backgroundColor: colors.primary,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Ionicons name="add" size={24} color={colors.textOnPrimary} />
              </TouchableOpacity>
            </View>

            {/* Barra "N itens" — recolhida por padrão, toque abre a lista. */}
            {hasItems ? (
              <>
                <TouchableOpacity
                  onPress={() => toggleCat(category.id)}
                  activeOpacity={0.7}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: colors.surfaceAlt,
                    paddingHorizontal: spacing.md,
                    paddingVertical: spacing.sm + 1,
                  }}
                >
                  <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "600" }]}>
                    {categoryItems.length} {categoryItems.length === 1 ? "item" : "itens"}
                  </Text>
                  <Ionicons name={isOpen ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
                </TouchableOpacity>

                {isOpen ? (
                  <View style={{ paddingHorizontal: spacing.md, paddingBottom: spacing.sm }}>
                    {categoryItems.map(({ item, mealLogId }) => (
                      <View
                        key={item.id}
                        style={{
                          flexDirection: "row",
                          alignItems: "center",
                          paddingVertical: spacing.sm,
                          borderBottomWidth: 1,
                          borderBottomColor: colors.border,
                        }}
                      >
                        {/* Toque no alimento = corrigir a quantidade. */}
                        <TouchableOpacity
                          onPress={() => openEditor(item)}
                          activeOpacity={0.7}
                          style={{ flex: 1, flexDirection: "row", alignItems: "center", gap: 6 }}
                        >
                          <View style={{ flex: 1 }}>
                            <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]} numberOfLines={1}>
                              {item.food.name}
                            </Text>
                            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                              {formatQuantity(item.quantity_g, item.unit_label, item.unit_amount)} · {Math.round(item.kcal)} kcal
                            </Text>
                          </View>
                          <Ionicons name="create-outline" size={16} color={colors.textSecondary} />
                        </TouchableOpacity>
                        <TouchableOpacity
                          onPress={() =>
                            setDeleteTarget({
                              mealLogId,
                              foodName: item.food.name,
                              itemCount: meals.find((m) => m.id === mealLogId)?.items.length ?? 1,
                            })
                          }
                          hitSlop={8}
                          style={{ marginLeft: spacing.md }}
                        >
                          <Ionicons name="close-circle" size={19} color={colors.textSecondary} />
                        </TouchableOpacity>
                      </View>
                    ))}
                  </View>
                ) : null}
              </>
            ) : null}
          </Card>
        );
      })}

      {/* Dietas prontas (Free) — discovery, abaixo das refeições. */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("DietTemplates")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.moduleNutrition,
          borderRadius: radius.card,
          padding: spacing.md,
          marginTop: spacing.sm,
        }}
      >
        <View
          style={{
            width: 40,
            height: 40,
            borderRadius: 13,
            backgroundColor: "rgba(255,255,255,0.22)",
            alignItems: "center",
            justifyContent: "center",
            marginRight: spacing.md,
          }}
        >
          <Ionicons name="restaurant" size={20} color="#FFFFFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[type.bodySmall, { color: "#FFFFFF", fontWeight: "700" }]}>Dietas prontas</Text>
          <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={2}>
            Escolha um cardápio pronto e adapte ao seu dia
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#FFFFFF" />
      </TouchableOpacity>

      <ConfirmDialog
        visible={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title={deleteTarget && deleteTarget.itemCount > 1 ? "Remover esta refeição" : "Remover alimento"}
        message={
          deleteTarget
            ? deleteTarget.itemCount > 1
              ? `Este registro tem ${deleteTarget.itemCount} alimentos (incluindo "${deleteTarget.foodName}") e será removido inteiro do seu diário.`
              : `Remover "${deleteTarget.foodName}" do seu diário?`
            : undefined
        }
        confirmLabel="Remover"
        destructive
        onConfirm={confirmDeleteFood}
      />
      <InfoDialog
        visible={dayAviso !== null}
        onClose={() => setDayAviso(null)}
        title={dayAviso?.title ?? ""}
        message={dayAviso?.message}
      />

      {/* Editor de quantidade de um item já registrado (toque no alimento). */}
      {editing ? (
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
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 2 }]} numberOfLines={2}>
              {editing.food.name}
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Ajuste a quantidade — as calorias são recalculadas.
            </Text>
            <QuantityEditor food={editing.food} value={editQty} onChange={setEditQty} compact />
            <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg }}>
              <View style={{ flex: 1 }}>
                <Button title="Salvar" compact onPress={salvarEdicao} loading={savingEdit} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Cancelar" variant="ghost" compact onPress={() => setEditing(null)} />
              </View>
            </View>
          </Card>
        </KeyboardAvoidingView>
      ) : null}
    </ScrollView>
  );
}

/** Uma barra de macro compacta (usada em coluna dentro do resumo). */
function MacroBar({ label, value, goal, color }: { label: string; value: number; goal: number; color: string }) {
  const { colors, type } = useTheme();
  const progress = goal > 0 ? Math.min(value / goal, 1) : 0;
  return (
    <View style={{ flex: 1 }}>
      <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
        {label}
      </Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", marginBottom: 3 }]} numberOfLines={1}>
        {Math.round(value)}
        <Text style={{ color: colors.textSecondary, fontWeight: "400" }}>{goal > 0 ? `/${Math.round(goal)}g` : "g"}</Text>
      </Text>
      <View style={{ height: 5, backgroundColor: colors.surfaceAlt, borderRadius: 3 }}>
        <View style={{ height: 5, width: `${progress * 100}%`, backgroundColor: color, borderRadius: 3 }} />
      </View>
    </View>
  );
}
