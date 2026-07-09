import { createNavigationContainerRef } from "@react-navigation/native";

/** Ref global de navegação — permite navegar de fora de uma tela (ex: o
 * indicador de "treino em andamento", que fica sobreposto ao app inteiro). */
export const navigationRef = createNavigationContainerRef<any>();
