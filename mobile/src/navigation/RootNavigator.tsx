import { Ionicons } from "@expo/vector-icons";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { ActivityIndicator, Animated, TouchableOpacity, View } from "react-native";

import { useActiveWorkout } from "../context/ActiveWorkoutContext";
import { useAuth } from "../context/AuthContext";
import { AiHubScreen } from "../screens/ai/AiHubScreen";
import { AssistantScreen } from "../screens/ai/AssistantScreen";
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
      <Stack.Screen name="Assistant" component={AssistantScreen} options={{ headerShown: true, title: "Assistente" }} />
      <Stack.Screen name="Chat" component={ChatScreen} options={{ presentation: "modal" }} />
    </Stack.Navigator>
  );
}

/** Indicador flutuante de "treino em andamento" — um ícone circular pequeno
 * no canto (não uma barra larga, pra não atrapalhar quem está usando outra
 * parte do app). Aparece em qualquer tela menos na própria execução; um pulso
 * sutil sinaliza que o treino está rolando. Toque volta pro treino. */
function ActiveWorkoutBadge() {
  const { colors } = useTheme();
  const { active, onWorkoutScreen } = useActiveWorkout();
  const pulse = React.useRef(new Animated.Value(0)).current;

  React.useEffect(() => {
    if (!active || onWorkoutScreen) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [active, onWorkoutScreen, pulse]);

  if (!active || onWorkoutScreen) return null;

  return (
    <View style={{ position: "absolute", left: 16, bottom: 24, width: 52, height: 52 }} pointerEvents="box-none">
      {/* anel que pulsa por trás do ícone */}
      <Animated.View
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 52,
          height: 52,
          borderRadius: 26,
          backgroundColor: colors.moduleTraining,
          opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0] }),
          transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.5] }) }],
        }}
      />
      <TouchableOpacity
        activeOpacity={0.85}
        accessibilityLabel={`Treino em andamento: ${active.routineName}. Toque para voltar.`}
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
          width: 52,
          height: 52,
          borderRadius: 26,
          backgroundColor: colors.moduleTraining,
          alignItems: "center",
          justifyContent: "center",
          shadowColor: "#000",
          shadowOffset: { width: 0, height: 3 },
          shadowOpacity: 0.25,
          shadowRadius: 6,
          elevation: 6,
        }}
      >
        <Ionicons name="barbell" size={24} color="#FFFFFF" />
      </TouchableOpacity>
    </View>
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
