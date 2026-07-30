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

// ATLAS — azul de performance + verde de progresso.
//
// A identidade é a mesma nos dois temas, e cada um tem o seu jeito de existir:
// o CLARO é ar e contorno (fundo gelo, superfície branca, borda fina dando a
// forma dos cards); o ESCURO é profundidade (azul-noite quase preto, superfície
// que sobe um degrau e brilho azul no lugar da sombra preta, que some no
// escuro). Não é o tema claro com as cores invertidas — são dois desenhos.
//
// O azul é o acento de marca e carrega ação: botão primário, item ativo, dado
// em destaque. O verde é reservado a PROGRESSO (evolução, meta batida, série
// concluída) — ele significa uma coisa só, então quando aparece a pessoa sabe
// o que aconteceu sem ler. A turquesa é o terceiro tom, pro que é secundário
// mas não é neutro. Cinza e branco cuidam de toda a estrutura.
//
// As cores de módulo são versões harmonizadas da mesma família: o dashboard
// precisa distinguir nutrição de treino de sono, não virar um arco-íris.

export const lightColors: ColorScheme = {
  primary: "#3563FF",
  primaryLight: "#6A8BFF",
  primaryDark: "#2246C9",
  primarySoft: "#E4EAFF",
  secondary: "#234E70",
  secondarySoft: "#DCE7F0",

  bg: "#F4F7FB",
  surface: "#FFFFFF",
  surfaceAlt: "#EDF1F7",
  textPrimary: "#0F172A",
  textSecondary: "#64748B",
  textOnPrimary: "#FFFFFF",
  border: "#DDE4EE",

  success: "#22C55E",
  warning: "#F59E0B",
  danger: "#E5484D",
  info: "#2DD4BF",

  moduleNutrition: "#22C55E",
  moduleTraining: "#3563FF",
  moduleSleep: "#6366F1",
  moduleSocial: "#2DD4BF",
};

export const darkColors: ColorScheme = {
  ...lightColors,
  // Azul-noite, não preto puro: o fundo tem a mesma temperatura do acento, o
  // que faz o azul brilhar em cima dele em vez de vibrar contra um preto neutro.
  // O acento sobe um tom pra manter contraste sobre superfície escura.
  primary: "#4F7CFF",
  primaryLight: "#89A6FF",
  primaryDark: "#3560DB",
  primarySoft: "#16224A",
  secondary: "#26608A",
  secondarySoft: "#132A3D",

  bg: "#081020",
  surface: "#111827",
  surfaceAlt: "#1B2233",
  textPrimary: "#E8EDF7",
  textSecondary: "#94A3B8",
  border: "#233047",

  success: "#34D399",
  warning: "#FBBF24",
  danger: "#F0575C",
  info: "#38E0C5",

  moduleNutrition: "#34D399",
  moduleTraining: "#4F7CFF",
  moduleSleep: "#818CF8",
  moduleSocial: "#38E0C5",
};
