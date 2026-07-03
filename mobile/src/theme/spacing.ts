export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radius = {
  button: 14,
  card: 20,
  pill: 999,
  modal: 24,
} as const;

// Sombras suaves para dar profundidade/elevação aos cards (iOS + Android + web).
export const shadow = {
  sm: {
    shadowColor: "#1A1F1C",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  md: {
    shadowColor: "#1A1F1C",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.1,
    shadowRadius: 18,
    elevation: 5,
  },
} as const;
