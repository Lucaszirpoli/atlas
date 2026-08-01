import { Ionicons } from "@expo/vector-icons";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { ActivityIndicator, Animated, TouchableOpacity, View } from "react-native";

import { useActiveWorkout } from "../context/ActiveWorkoutContext";
import { useAuth } from "../context/AuthContext";
import { AssistantScreen } from "../screens/ai/AssistantScreen";
import { ChatScreen } from "../screens/ai/ChatScreen";
import { CoachChatScreen } from "../screens/coaching/CoachChatScreen";
import { CoachingScreen } from "../screens/coaching/CoachingScreen";
import { EvolutionScreen } from "../screens/evolution/EvolutionScreen";
import { PaywallScreen } from "../screens/main/PaywallScreen";
import { ProfileScreen } from "../screens/main/ProfileScreen";
import { HomeLayoutScreen } from "../screens/settings/HomeLayoutScreen";
import { SleepScreen } from "../screens/sleep/SleepScreen";
import { WaterScreen } from "../screens/water/WaterScreen";
import { WeightScreen } from "../screens/weight/WeightScreen";
import { useTheme } from "../theme/ThemeProvider";
import { BrandSplash } from "../components/BrandSplash";
import { AuthStack } from "./AuthStack";
import { headerPadrao } from "./headerOptions";
import { navigationRef } from "./navigationRef";
import { voltarParaNaRaiz } from "./voltarPara";
import { NutritionStack } from "./NutritionStack";
import { SocialStack } from "./SocialStack";
import { TrainingStack } from "./TrainingStack";

const Stack = createNativeStackNavigator();

function AppStack() {
  const { colors } = useTheme();
  return (
    <Stack.Navigator screenOptions={{ ...headerPadrao(colors), headerShown: false }}>
      {/* Home = Coaching. É a primeira tela do app (Pro vê o hub; Free vê a
          grade de módulos). Sem header — a própria tela tem o seu cabeçalho. */}
      <Stack.Screen name="Home" component={CoachingScreen} />

      {/* Módulos abertos a partir da home */}
      <Stack.Screen name="NutritionModule" component={NutritionStack} />
      <Stack.Screen name="TrainingModule" component={TrainingStack} />
      <Stack.Screen name="Social" component={SocialStack} />

      {/* Telas individuais */}
      <Stack.Screen name="Sleep" component={SleepScreen} options={{ headerShown: true, title: "Sono" }} />
      <Stack.Screen name="Weight" component={WeightScreen} options={{ headerShown: true, title: "Peso" }} />
      <Stack.Screen name="Water" component={WaterScreen} options={{ headerShown: true, title: "Água" }} />
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ headerShown: true, title: "Perfil" }} />
      <Stack.Screen
        name="HomeLayout"
        component={HomeLayoutScreen}
        options={{ headerShown: true, title: "Layout da tela inicial" }}
      />
      <Stack.Screen name="Paywall" component={PaywallScreen} options={{ headerShown: true, title: "ATLAS Pro" }} />
      <Stack.Screen name="CoachChat" component={CoachChatScreen} options={{ headerShown: true, title: "Pergunte ao coach" }} />
      <Stack.Screen name="Evolution" component={EvolutionScreen} options={{ headerShown: true, title: "Evolução" }} />
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
  const { colors, shadow } = useTheme();
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
          // Reabre exatamente a tela de execução do treino em andamento.
          //
          // `voltarParaNaRaiz` e não `navigate`: o módulo de treino quase sempre
          // JÁ está na pilha (foi de lá que a pessoa minimizou o treino), e no
          // React Navigation 7 o navigate empilharia um segundo módulo em cima
          // do primeiro — a seta de voltar passaria a devolver pro anterior em
          // vez de sair.
          voltarParaNaRaiz(navigationRef as any, "TrainingModule", {
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
          ...shadow.md,
        }}
      >
        <Ionicons name="barbell-outline" size={24} color={colors.textOnPrimary} />
      </TouchableOpacity>
    </View>
  );
}

export function RootNavigator() {
  const { colors } = useTheme();
  const { isLoading, user } = useAuth();
  // A abertura da marca some sozinha quando a animação termina. Ela NÃO segura o
  // app: fica por cima enquanto a sessão é verificada e sai quando as duas
  // coisas acabaram — o que estiver mais lento manda. Antes, o app abria num
  // corte seco (ícone -> tela), e num boot rápido dava um pisca de spinner.
  const [aberturaVisivel, setAberturaVisivel] = React.useState(true);

  // Sem onboarding de entrada: criou a conta, cai direto no app. O objetivo é
  // definido depois, quando a pessoa entra no Coaching (fluxo sob demanda lá).
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {isLoading ? (
        <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
          <ActivityIndicator color={colors.primary} size="large" />
        </View>
      ) : (
        <NavigationContainer ref={navigationRef}>
          {!user ? <AuthStack /> : <AppStack />}
          {user ? <ActiveWorkoutBadge /> : null}
        </NavigationContainer>
      )}
      {aberturaVisivel ? (
        <BrandSplash pronto={!isLoading} onDone={() => setAberturaVisivel(false)} />
      ) : null}
    </View>
  );
}
