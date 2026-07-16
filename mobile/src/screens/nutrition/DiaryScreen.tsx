import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { deleteMealLog, listMealCategories, listMealsForDay, type MealCategory, type MealLog } from "../../api/meals";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ProgressRing } from "../../components/ProgressRing";
import { useTheme } from "../../theme/ThemeProvider";

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
  // itemCount = quantos alimentos aquele registro tem. O backend só apaga a
  // REFEIÇÃO inteira (não item a item), então a confirmação precisa dizer isso
  // quando o registro tem mais de um alimento — antes dizia "remover <alimento>"
  // e levava os outros junto sem avisar.
  const [deleteTarget, setDeleteTarget] = useState<
    { mealLogId: number; foodName: string; itemCount: number } | null
  >(null);

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
  const kcalProgress = kcalGoal > 0 ? consumed.kcal / kcalGoal : 0;
  const overGoal = kcalGoal > 0 && consumed.kcal > kcalGoal;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />}
      showsVerticalScrollIndicator={false}
    >
      {/* Atalhos — Meta em destaque (maior), Medidas compacto ao lado. */}
      <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate("GoalSettings")}
          style={{
            flex: 1,
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: spacing.sm,
            backgroundColor: colors.surface,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.card,
            paddingVertical: spacing.md,
          }}
        >
          <Ionicons name="flag" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>Minha meta</Text>
        </TouchableOpacity>
        <TouchableOpacity
          activeOpacity={0.85}
          onPress={() => navigation.navigate("Measurements")}
          style={{
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: spacing.xs,
            backgroundColor: colors.surface,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.card,
            paddingVertical: spacing.md,
            paddingHorizontal: spacing.md,
          }}
        >
          <Ionicons name="body" size={18} color={colors.textSecondary} />
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>Medidas</Text>
        </TouchableOpacity>
      </View>

      {/* Entrada ÚNICA de "montar dieta" — dentro dela ficam as duas formas:
          com IA (bate a meta de macros) e as dietas prontas curadas. */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("AiDiet")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.secondary,
          borderRadius: radius.card,
          padding: spacing.md,
          marginBottom: spacing.md,
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
          <Text style={[type.bodySmall, { color: "#FFFFFF", fontWeight: "700" }]}>Montar dieta</Text>
          <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={2}>
            Com IA (bate sua meta) ou escolha uma dieta pronta
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#FFFFFF" />
      </TouchableOpacity>

      {/* Resumo calórico + macros */}
      <Card style={{ marginBottom: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <ProgressRing
            size={120}
            strokeWidth={12}
            progress={kcalProgress}
            value={kcalGoal > 0 ? `${Math.round(consumed.kcal)}` : "—"}
            label={kcalGoal > 0 ? `/ ${Math.round(kcalGoal)} kcal` : "sem meta"}
            color={overGoal ? colors.warning : colors.primary}
          />
          <View style={{ flex: 1, marginLeft: spacing.lg }}>
            <MacroBar label="Proteína" value={consumed.protein} goal={goal?.protein_g ?? 0} color={colors.moduleTraining} />
            <MacroBar label="Carboidrato" value={consumed.carbs} goal={goal?.carbs_g ?? 0} color={colors.info} />
            <MacroBar label="Gordura" value={consumed.fat} goal={goal?.fat_g ?? 0} color={colors.warning} />
          </View>
        </View>
        {overGoal ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            Você passou um pouco da meta hoje — tudo bem, é só informação.
          </Text>
        ) : null}
        {!goal ? (
          <View style={{ marginTop: spacing.md }}>
            <Button title="Definir meta de calorias" onPress={() => navigation.navigate("GoalSettings")} />
          </View>
        ) : null}
      </Card>

      {/* Água — fica aqui junto das calorias, que é onde a pessoa anota o que
          consumiu no dia. Toque nos atalhos pra registrar. */}
      <Card style={{ marginBottom: spacing.md }}>
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

      {/* Refeições */}
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Refeições de hoje
      </Text>
      {categories.map((category) => {
        const categoryMeals = meals.filter((m) => m.meal_category_id === category.id);
        const categoryItems = categoryMeals.flatMap((m) => m.items.map((item) => ({ item, mealLogId: m.id })));
        const categoryKcal = categoryItems.reduce((s, x) => s + x.item.kcal, 0);
        return (
          <Card key={category.id} padded={false} style={{ marginBottom: spacing.md }}>
            <View style={{ padding: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <View
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 13,
                    backgroundColor: colors.primarySoft,
                    alignItems: "center",
                    justifyContent: "center",
                    marginRight: spacing.sm,
                  }}
                >
                  <Ionicons name={categoryIcon(category.name)} size={19} color={colors.primary} />
                </View>
                <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{category.name}</Text>
                <Text style={[type.bodySmall, { color: categoryKcal > 0 ? colors.primary : colors.textSecondary, fontWeight: "700" }]}>
                  {Math.round(categoryKcal)} kcal
                </Text>
              </View>

              {categoryItems.length > 0 ? (
                <View style={{ marginTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm }}>
                  {categoryItems.map(({ item, mealLogId }) => (
                    <View key={item.id} style={{ flexDirection: "row", alignItems: "center", paddingVertical: 5 }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]} numberOfLines={1}>
                        {item.food.name}
                        <Text style={{ color: colors.textSecondary }}> · {Math.round(item.quantity_g)}g</Text>
                      </Text>
                      <Text style={[type.bodySmall, { color: colors.textSecondary, marginRight: spacing.md }]}>
                        {Math.round(item.kcal)} kcal
                      </Text>
                      <TouchableOpacity
                        onPress={() =>
                          setDeleteTarget({
                            mealLogId,
                            foodName: item.food.name,
                            itemCount: meals.find((m) => m.id === mealLogId)?.items.length ?? 1,
                          })
                        }
                        hitSlop={8}
                      >
                        <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              ) : null}
            </View>

            <TouchableOpacity
              onPress={() => navigation.navigate("AddFood", { categoryId: category.id })}
              activeOpacity={0.7}
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "center",
                paddingVertical: spacing.sm + 2,
                backgroundColor: colors.surfaceAlt,
                gap: 6,
              }}
            >
              <Ionicons name="add-circle" size={18} color={colors.primary} />
              <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "700" }]}>Adicionar</Text>
            </TouchableOpacity>
          </Card>
        );
      })}

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
    </ScrollView>
  );
}

function MacroBar({ label, value, goal, color }: { label: string; value: number; goal: number; color: string }) {
  const { colors, type } = useTheme();
  const progress = goal > 0 ? Math.min(value / goal, 1) : 0;
  return (
    <View style={{ marginBottom: 10 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 3 }}>
        <Text style={[type.caption, { color: colors.textSecondary, flexShrink: 1 }]} numberOfLines={1}>
          {label}
        </Text>
        <Text
          style={[type.caption, { color: colors.textPrimary, fontWeight: "600", flexShrink: 0, marginLeft: 6 }]}
          numberOfLines={1}
        >
          {Math.round(value)}{goal > 0 ? `/${Math.round(goal)}g` : "g"}
        </Text>
      </View>
      <View style={{ height: 6, backgroundColor: colors.surfaceAlt, borderRadius: 3 }}>
        <View style={{ height: 6, width: `${progress * 100}%`, backgroundColor: color, borderRadius: 3 }} />
      </View>
    </View>
  );
}
