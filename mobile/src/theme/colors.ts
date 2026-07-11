export type ColorScheme = {
  primary: string;
  primaryLight: string;
  primaryDark: string;
  primarySoft: string;
  secondary: string;
  secondarySoft: string;

  bg: string;
  surface: string;
  surfaceAlt: string;
  textPrimary: string;
  textSecondary: string;
  textOnPrimary: string;
  border: string;

  success: string;
  warning: string;
  danger: string;
  info: string;

  moduleNutrition: string;
  moduleTraining: string;
  moduleSleep: string;
  moduleSocial: string;
};

// ATLAS — identidade preto + laranja, minimalista. O laranja é o ÚNICO
// acento de marca; preto/branco/cinza cuidam de toda a estrutura. As cores de
// módulo são versões harmonizadas (dessaturadas) pra manter o dashboard
// legível sem poluir a paleta. As cores semânticas (success/warning/danger)
// existem só pra dar significado a dado, não como acento visual.

export const lightColors: ColorScheme = {
  primary: "#FF6B2C",
  primaryLight: "#FF8A5A",
  primaryDark: "#D9531C",
  primarySoft: "#FFE7DA",
  secondary: "#E85D26",
  secondarySoft: "#FFE0D0",

  bg: "#FAFAF8",
  surface: "#FFFFFF",
  surfaceAlt: "#F1F1ED",
  textPrimary: "#17181A",
  textSecondary: "#6E7370",
  textOnPrimary: "#FFFFFF",
  border: "#E7E7E1",

  success: "#2FA37A",
  warning: "#E8A33D",
  danger: "#E5484D",
  info: "#5E93C9",

  moduleNutrition: "#FF6B2C",
  moduleTraining: "#F59E42",
  moduleSleep: "#7C86A8",
  moduleSocial: "#C77A8A",
};

export const darkColors: ColorScheme = {
  ...lightColors,
  // Preto de verdade com o laranja vibrante por cima — o coração da marca
  // ATLAS. O acento fica um tom mais aceso pra brilhar sobre o fundo escuro.
  primary: "#FF6B2C",
  primaryLight: "#FF8A5A",
  primaryDark: "#C24E1C",
  primarySoft: "#2A1509",
  secondary: "#F26A2E",
  secondarySoft: "#2A1509",

  bg: "#0A0A0B",
  surface: "#141416",
  surfaceAlt: "#1D1D21",
  textPrimary: "#F4F4F2",
  textSecondary: "#9A9A96",
  border: "#26262B",

  success: "#37C08D",
  info: "#5E93C9",

  moduleNutrition: "#FF7A45",
  moduleTraining: "#F5A24E",
  moduleSleep: "#8791B4",
  moduleSocial: "#D0899A",
};
