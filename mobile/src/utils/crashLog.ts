import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Caixa-preta de crash. O ErrorBoundary só pega erro de RENDER do React — não
 * pega erro nativo nem rejeição de promise, que é justamente o que deixa a tela
 * branca (a árvore inteira some sem o boundary ver). Um amigo do usuário viu
 * branco total, SEM mensagem nenhuma, mesmo com o ErrorBoundary no ar (v20) —
 * prova de que o erro escapa do React.
 *
 * Solução: um handler GLOBAL (ErrorUtils) que grava o erro no armazenamento
 * ANTES de o app morrer. Na próxima abertura, o app lê e MOSTRA — assim
 * descobrimos a causa mesmo sem plugar o aparelho no computador. É o mesmo
 * "instrumentar em vez de adivinhar" que resolveu a importação num round.
 */

const CHAVE = "@appfit/ultimo_crash";

type CrashSalvo = {
  mensagem: string;
  quando: string;
  /** true só quando o app REALMENTE morreu. Uma promise não tratada (a
   * chamada de rede que falhou sem catch) também é gravada aqui pra
   * diagnóstico, mas não fecha o app — e anunciar "o app fechou sozinho da
   * última vez" por causa dela é alarme falso: assusta a pessoa e faz ela
   * mandar pro suporte um erro que não aconteceu. */
  fatal: boolean;
};

/** Registra o handler global. Chamar UMA vez, no topo do App. */
export function instalarCrashLogger(): void {
  // ErrorUtils é uma global do React Native (não tipada). Guarda o handler
  // atual pra continuar chamando ele (senão o app perde o comportamento
  // padrão de erro).
  const g = globalThis as any;
  if (!g.ErrorUtils || g.__appfitCrashLoggerInstalado) return;
  g.__appfitCrashLoggerInstalado = true;

  const anterior = g.ErrorUtils.getGlobalHandler?.();
  g.ErrorUtils.setGlobalHandler((erro: any, fatal?: boolean) => {
    // Grava sem await (o handler é síncrono); a escrita segue em background.
    // Pode não completar num crash fatal instantâneo, mas pega a maioria.
    const payload: CrashSalvo = {
      mensagem: `${erro?.name ?? "Erro"}: ${erro?.message ?? String(erro)}${
        fatal ? " [fatal]" : ""
      }\n\n${(erro?.stack ?? "").split("\n").slice(0, 6).join("\n")}`,
      quando: new Date().toISOString(),
      fatal: fatal !== false,
    };
    AsyncStorage.setItem(CHAVE, JSON.stringify(payload)).catch(() => {});
    anterior?.(erro, fatal);
  });

  // Rejeição de promise não capturada: gravada pra diagnóstico, mas com
  // fatal=false. O app CONTINUA vivo depois de uma dessas (é quase sempre uma
  // chamada de rede sem catch), e tratá-la como crash fazia a abertura
  // seguinte anunciar "o app fechou sozinho da última vez" sem nada ter
  // fechado — um susto por um erro que a pessoa nem viu acontecer.
  //
  // Também não pode SOBRESCREVER um crash fatal ainda não visto: o fatal é o
  // que interessa, e apagá-lo com um erro de rede posterior apagaria a única
  // pista do que derrubou o app.
  const tracking = g.HermesInternal?.enablePromiseRejectionTracker;
  if (typeof tracking === "function") {
    tracking({
      allRejections: true,
      onUnhandled: async (_id: number, erro: any) => {
        try {
          const anteriorCru = await AsyncStorage.getItem(CHAVE);
          if (anteriorCru && (JSON.parse(anteriorCru) as CrashSalvo)?.fatal) return;
          await AsyncStorage.setItem(
            CHAVE,
            JSON.stringify({
              mensagem: `Promise não tratada: ${erro?.message ?? String(erro)}`,
              quando: new Date().toISOString(),
              fatal: false,
            } satisfies CrashSalvo)
          );
        } catch {
          // diagnóstico é melhor-esforço: nunca pode atrapalhar o app
        }
      },
    });
  }
}

export async function lerUltimoCrash(): Promise<CrashSalvo | null> {
  try {
    const cru = await AsyncStorage.getItem(CHAVE);
    return cru ? (JSON.parse(cru) as CrashSalvo) : null;
  } catch {
    return null;
  }
}

export async function limparUltimoCrash(): Promise<void> {
  try {
    await AsyncStorage.removeItem(CHAVE);
  } catch {
    // ignora
  }
}
