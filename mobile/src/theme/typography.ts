// Fontes carregadas via expo-font em App.tsx (Google Fonts: Inter + Space Grotesk).
//
// Inter carrega TODA a interface, incluindo os números grandes — é o que as duas
// referências de design usam ("SF Pro / Inter"), e é o que mantém dado e rótulo
// falando a mesma língua. Space Grotesk ficou só no logotipo ATLAS: uma fonte de
// marca aparecendo em número de dashboard tira a marca do lugar dela.
export const fontFamily = {
  display: "Inter_700Bold",
  displaySemibold: "Inter_600SemiBold",
  body: "Inter_400Regular",
  bodyMedium: "Inter_500Medium",
  bodySemibold: "Inter_600SemiBold",
  bodyBold: "Inter_700Bold",
  /** Só o logotipo ATLAS. Não usar em texto de tela. */
  wordmark: "SpaceGrotesk_700Bold",
} as const;

export const typeScale = {
  // Números grandes (peso, streak, calorias). letterSpacing negativo porque
  // Inter em tamanho display abre demais e o número perde densidade.
  display: { fontSize: 44, lineHeight: 52, fontFamily: fontFamily.display, letterSpacing: -1 },
  h1: { fontSize: 24, lineHeight: 30, fontFamily: fontFamily.bodyBold, letterSpacing: -0.4 },
  h2: { fontSize: 18, lineHeight: 24, fontFamily: fontFamily.bodySemibold, letterSpacing: -0.2 },
  body: { fontSize: 16, lineHeight: 22, fontFamily: fontFamily.body },
  bodySmall: { fontSize: 15, lineHeight: 20, fontFamily: fontFamily.body },
  caption: { fontSize: 13, lineHeight: 18, fontFamily: fontFamily.body },
} as const;
