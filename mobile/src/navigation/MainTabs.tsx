import { Ionicons } from "@expo/vector-icons";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import React from "react";
import { View } from "react-native";

import { AiFab } from "../components/AiFab";
import { HomeScreen } from "../screens/main/HomeScreen";
import { PlaceholderScreen } from "../screens/main/PlaceholderScreen";
import { ProfileScreen } from "../screens/main/ProfileScreen";
import { useTheme } from "../theme/ThemeProvider";
import { NutritionStack } from "./NutritionStack";

const Tab = createBottomTabNavigator();

const ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  Inicio: "home",
  Nutricao: "restaurant",
  Treino: "barbell",
  Social: "people",
  Perfil: "person",
};

export function MainTabs() {
  const { colors } = useTheme();

  return (
    <View style={{ flex: 1 }}>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textSecondary,
          tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
          tabBarIcon: ({ color, size }) => (
            <Ionicons name={ICONS[route.name]} color={color} size={size} />
          ),
        })}
      >
        <Tab.Screen name="Inicio" component={HomeScreen} options={{ title: "Início" }} />
        <Tab.Screen
          name="Nutricao"
          component={NutritionStack}
          options={{ title: "Nutrição", headerShown: false }}
        />
        <Tab.Screen name="Treino" options={{ title: "Treino" }}>
          {() => (
            <PlaceholderScreen
              title="Treino"
              subtitle="Biblioteca de exercícios e rotinas chegam na Fase 2."
            />
          )}
        </Tab.Screen>
        <Tab.Screen name="Social" options={{ title: "Social" }}>
          {() => (
            <PlaceholderScreen
              title="Social"
              subtitle="Amigos, feed e desafios chegam na Fase 5."
            />
          )}
        </Tab.Screen>
        <Tab.Screen name="Perfil" component={ProfileScreen} options={{ title: "Perfil" }} />
      </Tab.Navigator>
      <AiFab />
    </View>
  );
}
