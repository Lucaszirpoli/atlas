import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { listMealCategories, listMealsForDay, type MealCategory, type MealLog } from "../../api/meals";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { Button } from "../../components/Button";
import { ProgressRing } from "../../components/ProgressRing";
import { useTheme } from "../../theme/ThemeProvider";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const QUICK_WATER_AMOUNTS = [200, 300, 500];

export function DiaryScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [categories, setCategories] = useState<MealCategory[]>([]);
  const [meals, setMeals] = useState<MealLog[]>([]);
  const [goal, setGoal] = useState<CalorieGoal | null>(null);
  const [water, setWater] = useState<WaterSummary | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function loadAll() {
    const [cats, mealsForDay, currentGoal, waterSummary] = await Promise.all([
      listMealCategories(),
      listMealsForDay(todayIso()),
      getCurrentGoal(),
      getTodayWaterSummary(),
    ]);
    setCategories(cats);
    setMeals(mealsForDay);
    setGoal(currentGoal);
    setWater(waterSummary);
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

  async function handleQuickWater(amountMl: number) {
    await logWater(amountMl);
    const summary = await getTodayWaterSummary();
    setWater(summary);
  }

  const kcalConsumed = meals.reduce(
    (sum, meal) => sum + meal.items.reduce((s, i) => s + i.kcal, 0),
    0
  );
  const kcalGoal = goal?.kcal ?? 0;
  const kcalProgress = kcalGoal > 0 ? kcalConsumed / kcalGoal : 0;
  const overGoal = kcalGoal > 0 && kcalConsumed > kcalGoal;

  return (
    <ScrollView
      contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />}
    >
      <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: spacing.md, marginBottom: spacing.sm }}>
        <TouchableOpacity onPress={() => navigation.navigate("Measurements")}>
          <Text style={[type.caption, { color: colors.primary }]}>Medidas e fotos</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => navigation.navigate("GoalSettings")}>
          <Text style={[type.caption, { color: colors.primary }]}>Meta</Text>
        </TouchableOpacity>
      </View>

      <View style={{ alignItems: "center", marginBottom: spacing.lg }}>
        {goal ? (
          <ProgressRing
            progress={kcalProgress}
            value={`${Math.round(kcalConsumed)}`}
            label={`de ${Math.round(kcalGoal)} kcal`}
            color={overGoal ? colors.warning : colors.primary}
          />
        ) : (
          <View style={{ alignItems: "center" }}>
            <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
              Você ainda não definiu uma meta de calorias.
            </Text>
            <Button title="Definir meta" onPress={() => navigation.navigate("GoalSettings")} />
          </View>
        )}
        {overGoal ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            Você passou um pouco da meta hoje — isso não é um problema, é só uma informação.
          </Text>
        ) : null}
      </View>

      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          borderWidth: 1,
          borderColor: colors.border,
          padding: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <View>
          <Text style={[type.h2, { color: colors.textPrimary }]}>Água</Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
            {water?.total_ml_today ?? 0} / {water?.goal_ml ?? 0} ml
          </Text>
        </View>
        <View style={{ flexDirection: "row", gap: spacing.xs }}>
          {QUICK_WATER_AMOUNTS.map((amount) => (
            <TouchableOpacity
              key={amount}
              onPress={() => handleQuickWater(amount)}
              style={{
                borderWidth: 1,
                borderColor: colors.info,
                borderRadius: radius.button,
                paddingVertical: spacing.xs,
                paddingHorizontal: spacing.sm,
              }}
            >
              <Text style={[type.caption, { color: colors.info }]}>+{amount}ml</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {categories.map((category) => {
        const categoryMeals = meals.filter((m) => m.meal_category_id === category.id);
        const categoryKcal = categoryMeals.reduce(
          (sum, m) => sum + m.items.reduce((s, i) => s + i.kcal, 0),
          0
        );
        return (
          <View key={category.id} style={{ marginBottom: spacing.lg }}>
            <View
              style={{
                flexDirection: "row",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: spacing.sm,
              }}
            >
              <Text style={[type.h2, { color: colors.textPrimary }]}>{category.name}</Text>
              <Text style={[type.caption, { color: colors.textSecondary }]}>
                {Math.round(categoryKcal)} kcal
              </Text>
            </View>

            {categoryMeals.flatMap((m) => m.items).map((item) => (
              <View
                key={item.id}
                style={{
                  flexDirection: "row",
                  justifyContent: "space-between",
                  paddingVertical: spacing.xs,
                }}
              >
                <Text style={[type.bodySmall, { color: colors.textPrimary }]}>
                  {item.food.name} ({Math.round(item.quantity_g)}g)
                </Text>
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                  {Math.round(item.kcal)} kcal
                </Text>
              </View>
            ))}

            <TouchableOpacity
              onPress={() => navigation.navigate("AddFood", { categoryId: category.id })}
              style={{
                marginTop: spacing.xs,
                borderWidth: 1,
                borderColor: colors.border,
                borderStyle: "dashed",
                borderRadius: radius.button,
                paddingVertical: spacing.sm,
                alignItems: "center",
              }}
            >
              <Text style={[type.bodySmall, { color: colors.primary }]}>+ Adicionar alimento</Text>
            </TouchableOpacity>
          </View>
        );
      })}
    </ScrollView>
  );
}
