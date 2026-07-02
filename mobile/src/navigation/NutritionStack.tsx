import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";

import { AddFoodScreen } from "../screens/nutrition/AddFoodScreen";
import { BarcodeScannerScreen } from "../screens/nutrition/BarcodeScannerScreen";
import { DiaryScreen } from "../screens/nutrition/DiaryScreen";
import { GoalSettingsScreen } from "../screens/nutrition/GoalSettingsScreen";
import { MealPhotoScreen } from "../screens/nutrition/MealPhotoScreen";
import { MeasurementsScreen } from "../screens/nutrition/MeasurementsScreen";
import { useTheme } from "../theme/ThemeProvider";

const Stack = createNativeStackNavigator();

export function NutritionStack() {
  const { colors } = useTheme();

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.textPrimary,
      }}
    >
      <Stack.Screen name="Diary" component={DiaryScreen} options={{ title: "Nutrição" }} />
      <Stack.Screen name="AddFood" component={AddFoodScreen} options={{ title: "Adicionar alimento" }} />
      <Stack.Screen
        name="BarcodeScanner"
        component={BarcodeScannerScreen}
        options={{ title: "Escanear código de barras" }}
      />
      <Stack.Screen name="GoalSettings" component={GoalSettingsScreen} options={{ title: "Meta calórica" }} />
      <Stack.Screen
        name="MealPhoto"
        component={MealPhotoScreen}
        options={{ title: "Registrar por foto" }}
      />
      <Stack.Screen name="Measurements" component={MeasurementsScreen} options={{ title: "Medidas e fotos" }} />
    </Stack.Navigator>
  );
}
