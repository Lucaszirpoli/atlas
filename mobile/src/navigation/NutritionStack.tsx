import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";

import { HeaderBack } from "../components/HeaderBack";
import { AiDietScreen } from "../screens/ai/AiDietScreen";
import { AddFoodScreen } from "../screens/nutrition/AddFoodScreen";
import { BarcodeScannerScreen } from "../screens/nutrition/BarcodeScannerScreen";
import { CalorieHistoryScreen } from "../screens/nutrition/CalorieHistoryScreen";
import { DiaryScreen } from "../screens/nutrition/DiaryScreen";
import { DietTemplatesScreen } from "../screens/nutrition/DietTemplatesScreen";
import { FoodDetailScreen } from "../screens/nutrition/FoodDetailScreen";
import { GoalSettingsScreen } from "../screens/nutrition/GoalSettingsScreen";
import { MeasurementsScreen } from "../screens/nutrition/MeasurementsScreen";
import { QuickLogScreen } from "../screens/nutrition/QuickLogScreen";
import { useTheme } from "../theme/ThemeProvider";

const Stack = createNativeStackNavigator();

export function NutritionStack() {
  const { colors } = useTheme();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
        headerTintColor: colors.textPrimary,
        headerTitleStyle: { fontWeight: "700" },
      }}
    >
      <Stack.Screen
        name="Diary"
        component={DiaryScreen}
        options={{ title: "Dieta", headerLeft: () => <HeaderBack /> }}
      />
      <Stack.Screen name="AddFood" component={AddFoodScreen} options={{ title: "Adicionar alimento" }} />
      {/* Sem título: a ficha já mostra o nome do alimento em destaque no corpo,
          repetir na barra só rouba altura da tabela nutricional. */}
      <Stack.Screen name="FoodDetail" component={FoodDetailScreen} options={{ title: "" }} />
      <Stack.Screen name="QuickLog" component={QuickLogScreen} options={{ title: "Registrar por texto" }} />
      <Stack.Screen name="DietTemplates" component={DietTemplatesScreen} options={{ title: "Dietas prontas" }} />
      <Stack.Screen name="AiDiet" component={AiDietScreen} options={{ title: "Montar dieta" }} />
      <Stack.Screen
        name="BarcodeScanner"
        component={BarcodeScannerScreen}
        options={{ title: "Escanear código de barras" }}
      />
      <Stack.Screen name="GoalSettings" component={GoalSettingsScreen} options={{ title: "Meta calórica" }} />
      <Stack.Screen name="Measurements" component={MeasurementsScreen} options={{ title: "Medidas e fotos" }} />
      <Stack.Screen name="CalorieHistory" component={CalorieHistoryScreen} options={{ title: "Histórico de calorias" }} />
    </Stack.Navigator>
  );
}
