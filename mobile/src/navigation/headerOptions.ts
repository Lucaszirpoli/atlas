import type { NativeStackNavigationOptions } from "@react-navigation/native-stack";

/**
 * O cabeçalho padrão de TODOS os stacks do app.
 *
 * Existe pra não haver quatro cópias do mesmo bloco (root, nutrição, treino,
 * social) divergindo com o tempo — foi assim que o alinhamento do título passou
 * despercebido: mudar em um não mudava nos outros.
 *
 * `headerTitleAlign: "center"` é a única linha que não é só cosmética. O padrão
 * do native-stack no Android é encostar o título na seta de voltar, e aí "Dieta"
 * e "‹" viram um bloco só — dá pra ler como se o título fizesse parte do botão.
 * No meio, o título é título e a seta é botão. No iOS já era centralizado, então
 * isto também alinha as duas plataformas.
 */
export function headerPadrao(colors: {
  bg: string;
  textPrimary: string;
}): NativeStackNavigationOptions {
  return {
    headerStyle: { backgroundColor: colors.bg },
    headerShadowVisible: false,
    headerTintColor: colors.textPrimary,
    headerTitleAlign: "center",
    headerTitleStyle: { fontWeight: "700" },
  };
}
