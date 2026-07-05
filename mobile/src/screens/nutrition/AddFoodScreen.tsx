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

import { createCustomFood, searchFoods, type Food } from "../../api/foods";
import { logMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
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

  // Cadastro rápido de alimento que não existe na base (ataca o churn
  // "base de alimentos incompleta"). Valores por 100g.
  const [customMode, setCustomMode] = useState(false);
  const [custom, setCustom] = useState({ name: "", kcal: "", protein: "", carbs: "", fat: "" });
  const [isCreating, setIsCreating] = useState(false);

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
      setQuantityG(String(food.default_portion_g ?? 100));
    } catch (err: any) {
      Alert.alert("Não foi possível cadastrar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsCreating(false);
    }
  }

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
        setResults(await searchFoods(query.trim()));
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
    const factor = Number(quantityG || 0) / 100;
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Card style={{ marginBottom: spacing.md }}>
          <Text style={[type.h1, { color: colors.textPrimary }]}>{selectedFood.name}</Text>
          {selectedFood.brand ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>
              {selectedFood.brand}
            </Text>
          ) : null}

          <View style={{ flexDirection: "row", alignItems: "flex-end", marginTop: spacing.lg }}>
            <TextInput
              value={quantityG}
              onChangeText={(v) => setQuantityG(v.replace(/[^0-9.]/g, ""))}
              keyboardType="decimal-pad"
              style={[
                type.display,
                {
                  color: colors.primary,
                  borderBottomWidth: 3,
                  borderBottomColor: colors.primary,
                  minWidth: 110,
                  paddingVertical: 2,
                },
              ]}
            />
            <Text style={[type.h2, { color: colors.textSecondary, marginLeft: spacing.sm, marginBottom: 8 }]}>
              gramas
            </Text>
          </View>
          {selectedFood.default_portion_label ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
              Sugestão: {selectedFood.default_portion_label} ({selectedFood.default_portion_g}g)
            </Text>
          ) : null}
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

      <FlatList
        data={results}
        keyExtractor={(item) => String(item.id)}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => {
              setSelectedFood(item);
              setQuantityG(String(item.default_portion_g));
            }}
            style={({ pressed }) => ({
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderRadius: radius.button,
              padding: spacing.md,
              marginBottom: spacing.sm,
              opacity: pressed ? 0.8 : 1,
            })}
          >
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{item.name}</Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                {item.brand ? `${item.brand} · ` : ""}
                {Math.round(item.kcal_per_100g)} kcal/100g
              </Text>
            </View>
            <Ionicons name="add-circle" size={26} color={colors.primary} />
          </Pressable>
        )}
        ListFooterComponent={
          query.trim().length >= 2 && !isSearching ? (
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
          ) : null
        }
      />
    </View>
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
