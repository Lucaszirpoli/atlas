import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";

import { HeaderBack } from "../components/HeaderBack";
import { ExercisePickerScreen } from "../screens/training/ExercisePickerScreen";
import { RoutineBuilderScreen } from "../screens/training/RoutineBuilderScreen";
import { RoutineListScreen } from "../screens/training/RoutineListScreen";
import { WorkoutExecutionScreen } from "../screens/training/WorkoutExecutionScreen";
import { WorkoutInsightsScreen } from "../screens/training/WorkoutInsightsScreen";
import { WorkoutPreviewScreen } from "../screens/training/WorkoutPreviewScreen";
import { WorkoutSummaryScreen } from "../screens/training/WorkoutSummaryScreen";
import { useTheme } from "../theme/ThemeProvider";

const Stack = createNativeStackNavigator();

export function TrainingStack() {
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
        name="RoutineList"
        component={RoutineListScreen}
        options={{ title: "Treino", headerLeft: () => <HeaderBack /> }}
      />
      <Stack.Screen
        name="RoutineBuilder"
        component={RoutineBuilderScreen}
        options={{ title: "Rotina" }}
      />
      <Stack.Screen
        name="ExercisePicker"
        component={ExercisePickerScreen}
        options={{ title: "Escolher exercício" }}
      />
      <Stack.Screen
        name="WorkoutPreview"
        component={WorkoutPreviewScreen}
        options={{ title: "Prévia do treino" }}
      />
      <Stack.Screen
        name="WorkoutExecution"
        component={WorkoutExecutionScreen}
        // Voltar fica VISÍVEL: a pessoa pode "minimizar" o treino e sair da
        // aba — o indicador flutuante de "treino em andamento" (RootNavigator)
        // aparece nas outras telas e traz ela de volta num toque, sem perder
        // o progresso (a tela continua montada em segundo plano).
        options={{ title: "Treinando", headerBackTitle: "Minimizar" }}
      />
      <Stack.Screen
        name="WorkoutSummary"
        component={WorkoutSummaryScreen}
        options={{ title: "Resumo", headerBackVisible: false }}
      />
      <Stack.Screen
        name="WorkoutInsights"
        component={WorkoutInsightsScreen}
        options={{ title: "Reavaliação" }}
      />
    </Stack.Navigator>
  );
}
