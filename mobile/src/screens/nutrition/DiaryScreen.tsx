import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, RefreshControl, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { getNutritionHistory, type NutritionHistory } from "../../api/evolution";
import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { deleteMealLog, listMealCategories, listMealsForDay, type MealCategory, type MealLog } from "../../api/meals";
import { getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { AiEntryCard } from "../../components/AiEntryCard";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { ProgressRing } from "../../components/ProgressRing";
import { useTheme } from "../../theme/ThemeProvider";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const QUICK_WATER = [200, 300, 500];

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
  const [history, setHistory] = useState<NutritionHistory | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function loadAll() {
    const [cats, mealsForDay, currentGoal, waterSummary, hist] = await Promise.all([
      listMealCategories(),
      listMealsForDay(todayIso()),
      getCurrentGoal(),
      getTodayWaterSummary(),
      getNutritionHistory(14).catch(() => null),
    ]);
    setCategories(cats);
    setMeals(mealsForDay);
    setGoal(currentGoal);
    setWater(waterSummary);
    setHistory(hist);
  }

  async function handleDeleteFood(mealLogId: number, foodName: string) {
    Alert.alert("Remover alimento", `Remover "${foodName}" do seu diário?`, [
      { text: "Cancelar", style: "cancel" },
      {
        text: "Remover",
        style: "destructive",
        onPress: async () => {
          await deleteMealLog(mealLogId);
          loadAll();
        },
      },
    ]);
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
    setWater(await getTodayWaterSummary());
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
  const waterProgress = water && water.goal_ml > 0 ? water.total_ml_today / water.goal_ml : 0;

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

      {/* Entrada da IA — o recurso mais poderoso do módulo, em 1 toque */}
      <AiEntryCard
        title="Monte sua dieta com IA personalizada"
        subtitle="Diz seu objetivo e preferências — a IA monta pra você"
        prompt="Monte uma dieta personalizada pra mim, considerando meu objetivo, minhas preferências alimentares e minha rotina."
      />

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

      {/* Histórico 14 dias + adesão */}
      {history && history.days.length > 0 ? (
        <Card style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
            <Ionicons name="calendar" size={18} color={colors.primary} />
            <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1 }]}>Últimos 14 dias</Text>
            <HelpDot
              title="Janela de 14 dias"
              text={
                "Mostra quanto você comeu por dia nas últimas duas semanas. As barras dentro da meta ficam verdes; " +
                "as que passaram, laranja. A linha pontilhada é a sua meta de calorias."
              }
            />
          </View>
          <FourteenDayBars history={history} />
          {history.goal_kcal ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              {history.days_within_goal} de {history.days_logged}{" "}
              {history.days_logged === 1 ? "dia registrado" : "dias registrados"} dentro da meta
            </Text>
          ) : null}
        </Card>
      ) : null}

      {/* Água */}
      <Card accent={colors.info} style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Ionicons name="water" size={22} color={colors.info} />
            <View style={{ marginLeft: spacing.sm }}>
              <Text style={[type.h2, { color: colors.textPrimary }]}>
                {((water?.total_ml_today ?? 0) / 1000).toFixed(1)}L
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                  {"  "}/ {((water?.goal_ml ?? 0) / 1000).toFixed(1)}L
                </Text>
              </Text>
            </View>
            <HelpDot
              title="Meta de água"
              text={
                "Sua meta é calculada como 35ml por kg do seu peso atual — uma referência comum de hidratação. " +
                "Se você atualizar seu peso, a meta acompanha. Os botões +200/+300/+500 registram na hora."
              }
            />
          </View>
          <View style={{ flexDirection: "row", gap: spacing.xs }}>
            {QUICK_WATER.map((amount) => (
              <TouchableOpacity
                key={amount}
                onPress={() => handleQuickWater(amount)}
                style={{
                  borderRadius: radius.pill,
                  paddingVertical: 6,
                  paddingHorizontal: 12,
                  backgroundColor: colors.info + "1A",
                }}
              >
                <Text style={[type.caption, { color: colors.info, fontWeight: "700", fontSize: 11 }]}>+{amount}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
        {/* barra de progresso da água */}
        <View style={{ height: 8, backgroundColor: colors.surfaceAlt, borderRadius: 4, marginTop: spacing.md }}>
          <View
            style={{
              height: 8,
              width: `${Math.min(waterProgress, 1) * 100}%`,
              backgroundColor: colors.info,
              borderRadius: 4,
            }}
          />
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
                      <TouchableOpacity onPress={() => handleDeleteFood(mealLogId, item.food.name)} hitSlop={8}>
                        <Ionicons name="close-circle" size={18} color={colors.textSecondary} />
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              ) : null}
            </View>

            <View style={{ flexDirection: "row" }}>
              <TouchableOpacity
                onPress={() => navigation.navigate("AddFood", { categoryId: category.id })}
                activeOpacity={0.7}
                style={{
                  flex: 1,
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
              <TouchableOpacity
                onPress={() => navigation.navigate("QuickLog", { categoryId: category.id })}
                activeOpacity={0.7}
                style={{
                  flex: 1,
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "center",
                  paddingVertical: spacing.sm + 2,
                  backgroundColor: colors.surfaceAlt,
                  borderLeftWidth: 1,
                  borderLeftColor: colors.border,
                  gap: 6,
                }}
              >
                <Ionicons name="chatbox-ellipses" size={17} color={colors.secondary} />
                <Text style={[type.bodySmall, { color: colors.secondary, fontWeight: "700" }]}>Falar/escrever</Text>
              </TouchableOpacity>
            </View>
          </Card>
        );
      })}
    </ScrollView>
  );
}

function FourteenDayBars({ history }: { history: NutritionHistory }) {
  const { colors, type } = useTheme();
  const goal = history.goal_kcal ?? 0;
  const maxKcal = Math.max(...history.days.map((d) => d.kcal), goal, 1) * 1.1;
  const CHART_H = 90;

  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "flex-end", height: CHART_H, gap: 3, position: "relative" }}>
        {/* linha da meta */}
        {goal > 0 ? (
          <View
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              bottom: (goal / maxKcal) * CHART_H,
              borderTopWidth: 1,
              borderStyle: "dashed",
              borderColor: colors.primary,
              opacity: 0.6,
            }}
          />
        ) : null}
        {history.days.map((d) => {
          const h = d.kcal > 0 ? Math.max((d.kcal / maxKcal) * CHART_H, 3) : 2;
          const within = goal > 0 && d.kcal > 0 && d.kcal <= goal * 1.05;
          const over = goal > 0 && d.kcal > goal * 1.05;
          const color = d.kcal === 0 ? colors.surfaceAlt : over ? colors.warning : within ? colors.primary : colors.textSecondary;
          return <View key={d.date} style={{ flex: 1, height: h, backgroundColor: color, borderRadius: 3 }} />;
        })}
      </View>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: 4 }}>
        <Text style={[type.caption, { color: colors.textSecondary }]}>14 dias atrás</Text>
        <Text style={[type.caption, { color: colors.textSecondary }]}>hoje</Text>
      </View>
    </View>
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
