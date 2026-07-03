import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { ChatScreen } from "../screens/ai/ChatScreen";
import { EvolutionScreen } from "../screens/evolution/EvolutionScreen";
import { OnboardingScreen } from "../screens/onboarding/OnboardingScreen";
import { SleepScreen } from "../screens/sleep/SleepScreen";
import { useTheme } from "../theme/ThemeProvider";
import { AuthStack } from "./AuthStack";
import { MainTabs } from "./MainTabs";

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
      <Stack.Screen name="Main" component={MainTabs} />
      <Stack.Screen name="Chat" component={ChatScreen} options={{ presentation: "modal" }} />
      <Stack.Screen name="Sleep" component={SleepScreen} options={{ headerShown: true, title: "Sono" }} />
      <Stack.Screen
        name="Evolution"
        component={EvolutionScreen}
        options={{ headerShown: true, title: "Evolução" }}
      />
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
