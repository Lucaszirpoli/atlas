import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useColorScheme } from "react-native";

import { darkColors, lightColors, type ColorScheme } from "./colors";
import { radius, shadow, spacing } from "./spacing";
import { typeScale } from "./typography";

export type ThemeMode = "system" | "light" | "dark";

const STORAGE_KEY = "appfit.theme.mode";

type Theme = {
  colors: ColorScheme;
  type: typeof typeScale;
  spacing: typeof spacing;
  radius: typeof radius;
  shadow: typeof shadow;
  isDark: boolean;
  /** Preferência do usuário: acompanhar o sistema, ou forçar claro/escuro. */
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  /** Atalho: alterna direto entre claro e escuro (usado no toggle do topo). */
  toggleDark: () => void;
};

const ThemeContext = createContext<Theme | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const scheme = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>("system");

  // Carrega a preferência salva uma vez no início.
  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((saved) => {
      if (saved === "light" || saved === "dark" || saved === "system") {
        setModeState(saved);
      }
    });
  }, []);

  function setMode(next: ThemeMode) {
    setModeState(next);
    AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {});
  }

  const isDark = mode === "dark" || (mode === "system" && scheme === "dark");

  const theme = useMemo<Theme>(
    () => ({
      colors: isDark ? darkColors : lightColors,
      type: typeScale,
      spacing,
      radius,
      shadow,
      isDark,
      mode,
      setMode,
      toggleDark: () => setMode(isDark ? "light" : "dark"),
    }),
    [isDark, mode]
  );

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  const theme = useContext(ThemeContext);
  if (!theme) {
    throw new Error("useTheme precisa estar dentro de um ThemeProvider");
  }
  return theme;
}
