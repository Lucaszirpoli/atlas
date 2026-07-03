import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { ChatScreen } from "../screens/ai/ChatScreen";
import { EvolutionScreen } from "../screens/evolution/EvolutionScreen";
import { DashboardScreen } from "../screens/main/DashboardScreen";
import { ProfileScreen } from "../screens/main/ProfileScreen";
import { OnboardingScreen } from "../screens/onboarding/OnboardingScreen";
import { SleepScreen } from "../screens/sleep/SleepScreen";
import { WaterScreen } from "../screens/water/WaterScreen";
import { useTheme } from "../theme/ThemeProvider";
import { AuthStack } from "./AuthStack";
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
      <Stack.Screen name="Chat" component={ChatScreen} options={{ presentation: "modal" }} />
    </Stack.Navigator>
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

  return (
    <NavigationContainer>
      {!user ? <AuthStack /> : !user.onboarding_completed ? <OnboardingScreen /> : <AppStack />}
    </NavigationContainer>
  );
}
