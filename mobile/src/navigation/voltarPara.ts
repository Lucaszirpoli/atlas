import type { NavigationProp } from "@react-navigation/native";

/**
 * Volta para uma tela que JÁ ESTÁ na pilha, em vez de empilhar outra cópia.
 *
 * ## Por que isto existe
 *
 * O React Navigation 7 mudou o comportamento do `navigate`. Na versão 6, chamar
 * `navigate("Diary")` de uma tela mais acima na pilha VOLTAVA para o diário já
 * existente. Na 7, `navigate` empilha uma tela nova.
 *
 * O app foi escrito na 6 e atualizado para a 7, então todo "volta pro diário
 * depois de salvar" passou a deixar lixo embaixo:
 *
 *     [Diário] -> escolhe refeição -> [Diário, Buscar]
 *              -> abre o alimento  -> [Diário, Buscar, Alimento]
 *              -> salva            -> [Diário, Buscar, Alimento, Diário]
 *
 * A pessoa via o diário e achava que tinha voltado. Aí tocava na seta de voltar
 * e caía DENTRO do alimento que acabara de registrar — e de novo, e de novo, uma
 * vez por alimento que ela tivesse aberto na sessão. Era o loop relatado.
 *
 * `popTo` (API nova da 7) desempilha até a tela pedida, que é o que o `navigate`
 * da 6 fazia. Quando a tela não está na pilha — por exemplo, alguém entrou
 * direto na busca por um atalho —, cai no `navigate` normal, senão o `popTo`
 * lançaria e a pessoa ficaria presa.
 */
type Nav = NavigationProp<any> & {
  popTo?: (name: string, params?: object) => void;
  getParent?: () => Nav | undefined;
};

export function voltarPara(navigation: Nav, screen: string, params?: object): void {
  // Sobe pelos navegadores aninhados até achar quem tem a tela na pilha. A busca
  // no pai importa: as telas de nutrição e de treino vivem em stacks próprios
  // DENTRO do stack principal, então "voltar pra Home" a partir da meta calórica
  // atravessa dois navegadores. Sem subir, o helper cairia no `navigate` e
  // empilharia uma segunda Home — o mesmo bug, só que uma camada acima.
  let atual: Nav | undefined = navigation;
  for (let nivel = 0; atual && nivel < 5; nivel++) {
    const rotas = atual.getState?.()?.routes as { name: string }[] | undefined;
    if (rotas?.some((r) => r.name === screen) && typeof atual.popTo === "function") {
      atual.popTo(screen, params);
      return;
    }
    atual = atual.getParent?.();
  }
  // Não está em pilha nenhuma (alguém chegou aqui por um atalho): empilha
  // normalmente. `popTo` numa tela ausente lançaria e prenderia a pessoa.
  (navigation.navigate as (n: string, p?: object) => void)(screen, params);
}

/**
 * A mesma ideia para o `navigationRef` global (usado fora de uma tela, como no
 * indicador flutuante de treino em andamento).
 *
 * O ref não é um `navigation` de tela — não tem `popTo` nem `getParent` —,
 * então aqui a volta é despachada como ação de pilha sobre o estado raiz.
 * Sem isso, tocar no indicador empilhava um segundo módulo de treino em cima do
 * que já estava aberto, e a seta de voltar devolvia a pessoa pro anterior.
 */
export function voltarParaNaRaiz(
  ref: {
    isReady: () => boolean;
    getRootState: () => { routes?: { name: string }[] } | undefined;
    dispatch: (action: unknown) => void;
    navigate: (...args: never[]) => void;
  },
  screen: string,
  params?: object
): void {
  if (!ref.isReady()) return;
  const naRaiz = ref.getRootState()?.routes?.some((r) => r.name === screen);
  if (naRaiz) {
    // Import local: `StackActions` só é necessário neste caminho, e deixar o
    // import no topo obrigaria todo mundo que usa `voltarPara` a carregá-lo.
    const { StackActions } = require("@react-navigation/native");
    ref.dispatch(StackActions.popTo(screen, params));
    return;
  }
  (ref.navigate as unknown as (n: string, p?: object) => void)(screen, params);
}
