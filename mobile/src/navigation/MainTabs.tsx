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
import { SocialStack } from "./SocialStack";
import { TrainingStack } from "./TrainingStack";

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
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            borderTopWidth: 1,
            height: 64,
            paddingTop: 8,
            paddingBottom: 10,
          },
          tabBarLabelStyle: { fontSize: 11, fontWeight: "600", marginTop: 2 },
          tabBarIcon: ({ color, focused }) => (
            <Ionicons name={ICONS[route.name]} color={color} size={focused ? 25 : 23} />
          ),
        })}
      >
        <Tab.Screen name="Inicio" component={HomeScreen} options={{ title: "Início" }} />
        <Tab.Screen
          name="Nutricao"
          component={NutritionStack}
          options={{ title: "Nutrição", headerShown: false }}
        />
        <Tab.Screen
          name="Treino"
          component={TrainingStack}
          options={{ title: "Treino", headerShown: false }}
        />
        <Tab.Screen
          name="Social"
          component={SocialStack}
          options={{ title: "Social", headerShown: false }}
        />
        <Tab.Screen name="Perfil" component={ProfileScreen} options={{ title: "Perfil" }} />
      </Tab.Navigator>
      <AiFab />
    </View>
  );
}
