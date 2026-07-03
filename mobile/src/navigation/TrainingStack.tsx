import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";

import { ExercisePickerScreen } from "../screens/training/ExercisePickerScreen";
import { RoutineBuilderScreen } from "../screens/training/RoutineBuilderScreen";
import { RoutineListScreen } from "../screens/training/RoutineListScreen";
import { WorkoutExecutionScreen } from "../screens/training/WorkoutExecutionScreen";
import { WorkoutInsightsScreen } from "../screens/training/WorkoutInsightsScreen";
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
      <Stack.Screen name="RoutineList" component={RoutineListScreen} options={{ title: "Treino" }} />
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
        name="WorkoutExecution"
        component={WorkoutExecutionScreen}
        options={{ title: "Treinando", headerBackVisible: false }}
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
