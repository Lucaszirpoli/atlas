import { Ionicons } from "@expo/vector-icons";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { ActivityIndicator, Text, TouchableOpacity, View } from "react-native";

import { useActiveWorkout } from "../context/ActiveWorkoutContext";
import { useAuth } from "../context/AuthContext";
import { AiHubScreen } from "../screens/ai/AiHubScreen";
import { ChatScreen } from "../screens/ai/ChatScreen";
import { EvolutionScreen } from "../screens/evolution/EvolutionScreen";
import { DashboardScreen } from "../screens/main/DashboardScreen";
import { ProfileScreen } from "../screens/main/ProfileScreen";
import { OnboardingScreen } from "../screens/onboarding/OnboardingScreen";
import { SleepScreen } from "../screens/sleep/SleepScreen";
import { WaterScreen } from "../screens/water/WaterScreen";
import { useTheme } from "../theme/ThemeProvider";
import { AuthStack } from "./AuthStack";
import { navigationRef } from "./navigationRef";
import { NutritionStack } from "./NutritionStack";
import { SocialStack } from "./SocialStack";
import { TrainingStack } from "./TrainingStack";

const Stack = createNativeStackNavigator();

function AppStack() {
  const { colors } = useTheme();
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        headerStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
        headerTintColor: colors.textPrimary,
        headerTitleStyle: { fontWeight: "700" },
      }}
    >
      {/* Tela principal única */}
      <Stack.Screen name="Dashboard" component={DashboardScreen} />

      {/* Módulos abertos a partir das faixas */}
      <Stack.Screen name="NutritionModule" component={NutritionStack} />
      <Stack.Screen name="TrainingModule" component={TrainingStack} />
      <Stack.Screen name="Social" component={SocialStack} />

      {/* Telas individuais */}
      <Stack.Screen name="Sleep" component={SleepScreen} options={{ headerShown: true, title: "Sono" }} />
      <Stack.Screen name="Water" component={WaterScreen} options={{ headerShown: true, title: "Água" }} />
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ headerShown: true, title: "Perfil" }} />
      <Stack.Screen name="Evolution" component={EvolutionScreen} options={{ headerShown: true, title: "Evolução" }} />
      <Stack.Screen name="AiHub" component={AiHubScreen} options={{ headerShown: true, title: "Treino com IA" }} />
      <Stack.Screen name="Chat" component={ChatScreen} options={{ presentation: "modal" }} />
    </Stack.Navigator>
  );
}

/** Indicador flutuante de "treino em andamento" — aparece em qualquer tela
 * (menos na própria execução do treino) quando há um treino iniciado e não
 * concluído. Toque volta pro treino. Fica no canto, discreto. */
function ActiveWorkoutBadge() {
  const { colors, type } = useTheme();
  const { active, onWorkoutScreen } = useActiveWorkout();

  if (!active || onWorkoutScreen) return null;

  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={() => {
        if (!navigationRef.isReady()) return;
        // Reabre exatamente a tela de execução do treino em andamento.
        (navigationRef.navigate as any)("TrainingModule", {
          screen: "WorkoutExecution",
          params: {
            sessionId: active.sessionId,
            routineId: active.routineId,
            prefill: active.prefill,
          },
        });
      }}
      style={{
        position: "absolute",
        left: 16,
        bottom: 24,
        flexDirection: "row",
        alignItems: "center",
        gap: 8,
        backgroundColor: colors.moduleTraining,
        borderRadius: 999,
        paddingVertical: 10,
        paddingHorizontal: 14,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 3 },
        shadowOpacity: 0.25,
        shadowRadius: 6,
        elevation: 6,
        maxWidth: 260,
      }}
    >
      <Ionicons name="barbell" size={18} color="#FFFFFF" />
      <View style={{ flexShrink: 1 }}>
        <Text style={[type.caption, { color: "#FFFFFF", fontWeight: "800" }]} numberOfLines={1}>
          Treino em andamento
        </Text>
        <Text style={[type.caption, { color: "rgba(255,255,255,0.85)", fontSize: 11 }]} numberOfLines={1}>
          {active.routineName} · toque pra voltar
        </Text>
      </View>
    </TouchableOpacity>
  );
}

export function RootNavigator() {
  const { colors } = useTheme();
  const { isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  const showApp = user && user.onboarding_completed;

  return (
    <NavigationContainer ref={navigationRef}>
      {!user ? <AuthStack /> : !user.onboarding_completed ? <OnboardingScreen /> : <AppStack />}
      {showApp ? <ActiveWorkoutBadge /> : null}
    </NavigationContainer>
  );
}
