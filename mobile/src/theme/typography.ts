// Fontes carregadas via expo-font em App.tsx (Google Fonts: Inter + Space Grotesk).
export const fontFamily = {
  display: "SpaceGrotesk_700Bold",
  displaySemibold: "SpaceGrotesk_600SemiBold",
  body: "Inter_400Regular",
  bodyMedium: "Inter_500Medium",
  bodySemibold: "Inter_600SemiBold",
  bodyBold: "Inter_700Bold",
} as const;

export const typeScale = {
  display: { fontSize: 44, lineHeight: 52, fontFamily: fontFamily.display },
  h1: { fontSize: 24, lineHeight: 30, fontFamily: fontFamily.bodyBold },
  h2: { fontSize: 18, lineHeight: 24, fontFamily: fontFamily.bodySemibold },
  body: { fontSize: 16, lineHeight: 22, fontFamily: fontFamily.body },
  bodySmall: { fontSize: 15, lineHeight: 20, fontFamily: fontFamily.body },
  caption: { fontSize: 13, lineHeight: 18, fontFamily: fontFamily.body },
} as const;
