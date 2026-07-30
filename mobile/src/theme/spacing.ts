// Grade de 8pt — o mesmo passo das duas referências de design.
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
  card: 18,
  /** Campos de texto e seletores — um degrau abaixo do card que os contém. */
  input: 12,
  /** Etiquetas e badges pequenos, onde o raio de card ficaria redondo demais. */
  chip: 10,
  pill: 999,
  modal: 24,
} as const;

export type Elevation = {
  shadowColor: string;
  shadowOffset: { width: number; height: number };
  shadowOpacity: number;
  shadowRadius: number;
  elevation: number;
};

/** Elevação dos cards, por tema.
 *
 * Sombra preta não existe no escuro: preto sobre azul-noite não produz sombra
 * nenhuma, e o card ficava chapado, colado no fundo — era metade do "parece
 * HTML". No tema escuro a profundidade vem de duas coisas que o claro não
 * precisa: a superfície ser um degrau mais clara que o fundo (ver colors.ts) e
 * um halo azul de baixíssima opacidade, que é como as referências escuras
 * separam os cards.
 */
export function makeShadow(isDark: boolean): { sm: Elevation; md: Elevation } {
  if (isDark) {
    return {
      sm: {
        shadowColor: "#4F7CFF",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.1,
        shadowRadius: 10,
        elevation: 2,
      },
      md: {
        shadowColor: "#4F7CFF",
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.16,
        shadowRadius: 22,
        elevation: 6,
      },
    };
  }
  return {
    sm: {
      shadowColor: "#0F172A",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.06,
      shadowRadius: 8,
      elevation: 2,
    },
    md: {
      shadowColor: "#0F172A",
      shadowOffset: { width: 0, height: 10 },
      shadowOpacity: 0.1,
      shadowRadius: 22,
      elevation: 6,
    },
  };
}

// Compatibilidade: o tema claro é o padrão de leitura de quem importa `shadow`
// direto. Quem usa `useTheme().shadow` recebe a versão do tema ativo.
export const shadow = makeShadow(false);
