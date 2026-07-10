import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { deleteMealLog, listMealCategories, listMealsForDay, type MealCategory, type MealLog } from "../../api/meals";
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
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ mealLogId: number; foodName: string } | null>(null);

  async function loadAll() {
    const [cats, mealsForDay, currentGoal] = await Promise.all([
      listMealCategories(),
      listMealsForDay(todayIso()),
      getCurrentGoal(),
    ]);
    setCategories(cats);
    setMeals(mealsForDay);
    setGoal(currentGoal);
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
      {/* Atalhos */}
      <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: spacing.sm, marginBottom: spacing.md }}>
        <HeaderChip icon="body" label="Medidas" onPress={() => navigation.navigate("Measurements")} />
        <HeaderChip icon="flag" label="Meta" onPress={() => navigation.navigate("GoalSettings")} />
      </View>

      {/* Entrada compacta pras dietas semi-prontas (NÃO é IA — são moldes
          curados que o app escala pra bater com a meta calórica da pessoa). */}
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => navigation.navigate("DietTemplates")}
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          borderRadius: radius.card,
          paddingVertical: spacing.sm,
          paddingHorizontal: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <Ionicons name="restaurant-outline" size={18} color={colors.secondary} />
        <View style={{ flex: 1, marginLeft: spacing.sm }}>
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>Dietas prontas</Text>
          <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
            Clássica, low carb, alta proteína… já ajustadas pra sua meta
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
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
                      <TouchableOpacity onPress={() => setDeleteTarget({ mealLogId, foodName: item.food.name })} hitSlop={8}>
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
        title="Remover alimento"
        message={deleteTarget ? `Remover "${deleteTarget.foodName}" do seu diário?` : undefined}
        confirmLabel="Remover"
        destructive
        onConfirm={confirmDeleteFood}
      />
    </ScrollView>
  );
}

function HeaderChip({
  icon,
  label,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
}) {
  const { colors, type, radius, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        backgroundColor: colors.surface,
        borderRadius: radius.pill,
        paddingVertical: 8,
        paddingHorizontal: spacing.md,
        borderWidth: 1,
        borderColor: colors.border,
      }}
    >
      <Ionicons name={icon} size={15} color={colors.primary} />
      <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "600" }]}>{label}</Text>
    </TouchableOpacity>
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
