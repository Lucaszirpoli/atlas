import { useNavigation, useRoute } from "@react-navigation/native";
import { CameraView, useCameraPermissions } from "expo-camera";
import React, { useRef, useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import { analyzeMealPhoto, type MealPhotoItem } from "../../api/ai";
import { logMeal } from "../../api/meals";
import { Button } from "../../components/Button";
import { useTheme } from "../../theme/ThemeProvider";

export function MealPhotoScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId } = route.params ?? {};

  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const [items, setItems] = useState<(MealPhotoItem & { quantidade_editada: string })[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleCapture() {
    if (!cameraRef.current) return;
    setIsAnalyzing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ base64: true, quality: 0.6 });
      if (!photo?.base64) return;
      const result = await analyzeMealPhoto(photo.base64);
      setAviso(result.aviso);
      setItems(
        result.itens.map((i) => ({ ...i, quantidade_editada: String(i.quantidade_estimada_g) }))
      );
    } catch (err: any) {
      Alert.alert("Não foi possível analisar a foto", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsAnalyzing(false);
    }
  }

  function updateQuantity(index: number, value: string) {
    setItems((prev) =>
      prev ? prev.map((item, i) => (i === index ? { ...item, quantidade_editada: value } : item)) : prev
    );
  }

  async function handleConfirm() {
    if (!items) return;
    const recognized = items.filter((i) => i.food_id != null && Number(i.quantidade_editada) > 0);
    if (recognized.length === 0) {
      Alert.alert("Nada para registrar", "Nenhum item foi reconhecido na base de alimentos.");
      return;
    }
    setIsSubmitting(true);
    try {
      await logMeal({
        meal_category_id: categoryId,
        logged_at: new Date().toISOString(),
        items: recognized.map((i) => ({ food_id: i.food_id as number, quantity_g: Number(i.quantidade_editada) })),
      });
      navigation.navigate("Diary");
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!permission) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }
  if (!permission.granted) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.lg, backgroundColor: colors.bg }}>
        <Text style={[type.body, { color: colors.textPrimary, textAlign: "center", marginBottom: spacing.md }]}>
          Precisamos da câmera para reconhecer sua refeição.
        </Text>
        <Button title="Permitir câmera" onPress={requestPermission} />
      </View>
    );
  }

  if (items) {
    return (
      <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
        <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
          Confira antes de salvar
        </Text>
        {aviso ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>{aviso}</Text>
        ) : null}

        {items.map((item, index) => (
          <View
            key={index}
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: item.food_id ? colors.border : colors.warning,
              padding: spacing.md,
              marginBottom: spacing.sm,
            }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{item.nome_identificado}</Text>
            {!item.food_id ? (
              <Text style={[type.caption, { color: colors.warning, marginBottom: spacing.xs }]}>
                Não encontramos esse alimento na base — não será registrado.
              </Text>
            ) : null}
            <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.xs }}>
              <TextInput
                value={item.quantidade_editada}
                onChangeText={(v) => updateQuantity(index, v.replace(/[^0-9.]/g, ""))}
                keyboardType="decimal-pad"
                editable={!!item.food_id}
                style={[
                  type.body,
                  {
                    color: colors.textPrimary,
                    borderWidth: 1,
                    borderColor: colors.border,
                    borderRadius: radius.button,
                    width: 80,
                    height: 40,
                    textAlign: "center",
                  },
                ]}
              />
              <Text style={[type.bodySmall, { color: colors.textSecondary, marginLeft: spacing.sm }]}>
                gramas (confiança: {item.confianca})
              </Text>
            </View>
          </View>
        ))}

        <View style={{ marginTop: spacing.lg }}>
          <Button title="Confirmar e registrar" onPress={handleConfirm} loading={isSubmitting} />
        </View>
        <View style={{ marginTop: spacing.sm }}>
          <Button title="Tirar outra foto" variant="ghost" onPress={() => setItems(null)} />
        </View>
      </ScrollView>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <CameraView ref={cameraRef} style={{ flex: 1 }} />
      <View style={{ padding: spacing.lg, backgroundColor: colors.bg }}>
        <Button title="Tirar foto da refeição" onPress={handleCapture} loading={isAnalyzing} />
      </View>
    </View>
  );
}
