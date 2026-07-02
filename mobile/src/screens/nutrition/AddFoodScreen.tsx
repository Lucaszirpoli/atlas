import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";

import { searchFoods, type Food } from "../../api/foods";
import { logMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

export function AddFoodScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId, barcodeResult } = route.params ?? {};
  const { user } = useAuth();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Food[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedFood, setSelectedFood] = useState<Food | null>(null);
  const [quantityG, setQuantityG] = useState("100");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (barcodeResult) {
      setSelectedFood(barcodeResult);
      setQuantityG(String(barcodeResult.default_portion_g ?? 100));
    }
  }, [barcodeResult]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    const timeout = setTimeout(async () => {
      try {
        const foods = await searchFoods(query.trim());
        setResults(foods);
      } finally {
        setIsSearching(false);
      }
    }, 350);
    return () => clearTimeout(timeout);
  }, [query]);

  async function handleConfirm() {
    if (!selectedFood) return;
    const qty = Number(quantityG);
    if (!qty || qty <= 0) {
      Alert.alert("Quantidade inválida", "Informe a quantidade em gramas.");
      return;
    }
    setIsSubmitting(true);
    try {
      await logMeal({
        meal_category_id: categoryId,
        logged_at: new Date().toISOString(),
        items: [{ food_id: selectedFood.id, quantity_g: qty }],
      });
      navigation.goBack();
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (selectedFood) {
    const factor = Number(quantityG || 0) / 100;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
          {selectedFood.name}
        </Text>
        {selectedFood.brand ? (
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.md }]}>
            {selectedFood.brand}
          </Text>
        ) : null}

        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
          Quantidade (g)
        </Text>
        <TextInput
          value={quantityG}
          onChangeText={(v) => setQuantityG(v.replace(/[^0-9.]/g, ""))}
          keyboardType="decimal-pad"
          style={[
            type.display,
            {
              color: colors.textPrimary,
              borderBottomWidth: 2,
              borderBottomColor: colors.primary,
              marginBottom: spacing.lg,
              paddingVertical: spacing.xs,
            },
          ]}
        />

        <View
          style={{
            backgroundColor: colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.md,
            marginBottom: spacing.lg,
          }}
        >
          <NutrientRow label="Calorias" value={`${Math.round(selectedFood.kcal_per_100g * factor)} kcal`} />
          <NutrientRow label="Proteína" value={`${(selectedFood.protein_g_per_100g * factor).toFixed(1)} g`} />
          <NutrientRow label="Carboidrato" value={`${(selectedFood.carbs_g_per_100g * factor).toFixed(1)} g`} />
          <NutrientRow label="Gordura" value={`${(selectedFood.fat_g_per_100g * factor).toFixed(1)} g`} />
        </View>

        <Button title="Adicionar à refeição" onPress={handleConfirm} loading={isSubmitting} />
        <View style={{ marginTop: spacing.sm }}>
          <Button title="Cancelar" variant="ghost" onPress={() => setSelectedFood(null)} />
        </View>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Buscar alimento..."
        placeholderTextColor={colors.textSecondary}
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            height: 48,
            marginBottom: spacing.sm,
            backgroundColor: colors.surface,
          },
        ]}
      />

      <Button
        title="Escanear código de barras"
        variant="ghost"
        onPress={() => navigation.navigate("BarcodeScanner", { categoryId })}
      />
      <Button
        title={user?.plan === "pro" ? "Registrar por foto (IA)" : "Registrar por foto — exclusivo Pro"}
        variant="ghost"
        onPress={() => {
          if (user?.plan !== "pro") {
            Alert.alert(
              "Exclusivo do Pro",
              "Assine o Pro para registrar refeições automaticamente por foto."
            );
            return;
          }
          navigation.navigate("MealPhoto", { categoryId });
        }}
      />

      {isSearching ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.md }} /> : null}

      <FlatList
        data={results}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingTop: spacing.md }}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => {
              setSelectedFood(item);
              setQuantityG(String(item.default_portion_g));
            }}
            style={{
              paddingVertical: spacing.sm,
              borderBottomWidth: 1,
              borderBottomColor: colors.border,
            }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{item.name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {item.brand ? `${item.brand} · ` : ""}
              {Math.round(item.kcal_per_100g)} kcal/100g
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}

function NutrientRow({ label, value }: { label: string; value: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row",
        justifyContent: "space-between",
        paddingVertical: spacing.xs,
      }}
    >
      <Text style={[type.bodySmall, { color: colors.textSecondary }]}>{label}</Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary }]}>{value}</Text>
    </View>
  );
}
