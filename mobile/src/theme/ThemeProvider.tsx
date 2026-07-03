import React, { createContext, useContext, useMemo } from "react";
import { useColorScheme } from "react-native";

import { darkColors, lightColors, type ColorScheme } from "./colors";
import { radius, shadow, spacing } from "./spacing";
import { typeScale } from "./typography";

type Theme = {
  colors: ColorScheme;
  type: typeof typeScale;
  spacing: typeof spacing;
  radius: typeof radius;
  shadow: typeof shadow;
  isDark: boolean;
};

const ThemeContext = createContext<Theme | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const scheme = useColorScheme();
  const isDark = scheme === "dark";

  const theme = useMemo<Theme>(
    () => ({
      colors: isDark ? darkColors : lightColors,
      type: typeScale,
      spacing,
      radius,
      shadow,
      isDark,
    }),
    [isDark]
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
