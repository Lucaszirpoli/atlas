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

export const lightColors: ColorScheme = {
  primary: "#1F7A5C",
  primaryLight: "#2FA37A",
  primaryDark: "#145C43",
  primarySoft: "#E4F1EB",
  secondary: "#FF6B35",
  secondarySoft: "#FFE9DF",

  bg: "#F4F6F3",
  surface: "#FFFFFF",
  surfaceAlt: "#F0F3EF",
  textPrimary: "#1A1F1C",
  textSecondary: "#6B7570",
  textOnPrimary: "#FFFFFF",
  border: "#E8EBE6",

  success: "#2FA37A",
  warning: "#E8A33D",
  danger: "#D64545",
  info: "#3B82C4",

  moduleNutrition: "#1F7A5C",
  moduleTraining: "#FF6B35",
  moduleSleep: "#4A5B8C",
  moduleSocial: "#E8637A",
};

export const darkColors: ColorScheme = {
  ...lightColors,
  primarySoft: "#17352A",
  secondarySoft: "#3A2418",
  bg: "#0E1311",
  surface: "#1B211D",
  surfaceAlt: "#232B26",
  textPrimary: "#F2F4F1",
  textSecondary: "#9AA69F",
  border: "#2A312C",
};
