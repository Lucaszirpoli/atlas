import { Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold } from "@expo-google-fonts/inter";
import { SpaceGrotesk_600SemiBold, SpaceGrotesk_700Bold } from "@expo-google-fonts/space-grotesk";
import { useFonts } from "expo-font";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { View } from "react-native";

import { iniciarAquecimento } from "./src/api/warmup";
import { ErrorBoundary } from "./src/components/ErrorBoundary";
import { ActiveWorkoutProvider } from "./src/context/ActiveWorkoutContext";
import { AuthProvider } from "./src/context/AuthContext";
import { RootNavigator } from "./src/navigation/RootNavigator";
import { ThemeProvider } from "./src/theme/ThemeProvider";
import { instalarCrashLogger } from "./src/utils/crashLog";

// No topo do módulo (antes de qualquer render): captura erro nativo/async que
// escapa do ErrorBoundary e grava pra mostrar na próxima abertura.
instalarCrashLogger();

SplashScreen.preventAutoHideAsync();

export default function App() {
  const [fontsLoaded] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    SpaceGrotesk_600SemiBold,
    SpaceGrotesk_700Bold,
  });

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  // Acorda o backend enquanto a pessoa ainda está abrindo o app, pra o primeiro
  // toque não pagar o tempo de o servidor sair da hibernação. Ver api/warmup.
  useEffect(() => iniciarAquecimento(), []);

  if (!fontsLoaded) {
    // NUNCA retornar null aqui: null renderiza NADA e o Android mostra o fundo
    // nativo BRANCO — indistinguível de um crash. Uma View escura mantém o
    // splash coerente e garante que "branco total" só possa significar erro
    // de verdade, não "fontes carregando".
    //
    // A cor é a MESMA do splash nativo em app.json (darkColors.bg): é o que faz
    // a passagem splash nativo -> app não ter um pisca de cor no meio.
    return <View style={{ flex: 1, backgroundColor: "#081020" }} />;
  }

  return (
    // ErrorBoundary por FORA de tudo: se qualquer provider ou tela quebrar no
    // render, mostra o erro em vez de tela branca. Foi o que faltou quando um
    // amigo criou conta nova e viu só branco, sem pista nenhuma.
    <ErrorBoundary>
      <SafeAreaProvider>
        <ThemeProvider>
          <AuthProvider>
            <ActiveWorkoutProvider>
              <RootNavigator />
              <StatusBar style="auto" />
            </ActiveWorkoutProvider>
          </AuthProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}
