export type ColorScheme = {
  primary: string;
  primaryLight: string;
  primaryDark: string;
  secondary: string;

  bg: string;
  surface: string;
  textPrimary: string;
  textSecondary: string;
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
  secondary: "#FF6B35",

  bg: "#FAFAF8",
  surface: "#FFFFFF",
  textPrimary: "#1A1F1C",
  textSecondary: "#5C6660",
  border: "#E4E7E2",

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
  bg: "#121714",
  surface: "#1B211D",
  textPrimary: "#F2F4F1",
  textSecondary: "#9AA69F",
  border: "#2A312C",
};
