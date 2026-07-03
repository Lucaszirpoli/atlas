import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";

import { ChallengeDetailScreen } from "../screens/social/ChallengeDetailScreen";
import { ChallengesScreen } from "../screens/social/ChallengesScreen";
import { FriendsScreen } from "../screens/social/FriendsScreen";
import { PrivacyScreen } from "../screens/social/PrivacyScreen";
import { SocialFeedScreen } from "../screens/social/SocialFeedScreen";
import { useTheme } from "../theme/ThemeProvider";

const Stack = createNativeStackNavigator();

export function SocialStack() {
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
      <Stack.Screen name="SocialFeed" component={SocialFeedScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Friends" component={FriendsScreen} options={{ title: "Amigos" }} />
      <Stack.Screen name="Privacy" component={PrivacyScreen} options={{ title: "Privacidade" }} />
      <Stack.Screen name="Challenges" component={ChallengesScreen} options={{ title: "Desafios" }} />
      <Stack.Screen
        name="ChallengeDetail"
        component={ChallengeDetailScreen}
        options={{ title: "Placar" }}
      />
    </Stack.Navigator>
  );
}
