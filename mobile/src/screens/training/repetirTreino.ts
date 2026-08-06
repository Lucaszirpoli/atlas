/**
 * O aviso de "você já fez este treino nesta semana".
 *
 * Mora num arquivo só porque aparece em DOIS lugares (a lista de rotinas e a
 * prévia do treino) e precisa dizer exatamente a mesma coisa nos dois — um
 * aviso que muda de tom conforme a tela vira ruído.
 *
 * O tom é o da spec §3.7: nada de culpa, nada de bloqueio. Repetir um treino é
 * permitido e às vezes é a coisa certa (repor um dia perdido). O que a pessoa
 * precisa saber antes de tocar é que o volume da semana é planejado por músculo
 * e que uma repetição entra como volume ACIMA do planejado — quem decide é ela.
 */

export function tituloJaTreinou(feitos: number): string {
  return feitos > 1 ? `Você já fez este treino ${feitos}x essa semana` : "Você já treinou essa semana";
}

export const AVISO_REPETIR_TITULO = "Treinar este mesmo treino de novo?";

export function avisoRepetirMensagem(nome: string, feitos: number, doCoach: boolean): string {
  const quantas = feitos > 1 ? `${feitos} vezes` : "uma vez";
  const base =
    `Você já fez "${nome}" ${quantas} nesta semana. Pode treinar de novo, sem problema — ` +
    "só saiba que este treino entra como volume ACIMA do que estava planejado pra semana, " +
    "e é esse volume que eu uso pra medir sua recuperação e decidir suas cargas.";
  const doCoachExtra =
    " Como este treino foi montado pelo coach, ele já contava com a frequência da semana inteira; " +
    "repetir sai da recomendação. Se for pra repor um dia que você perdeu, faz sentido.";
  return doCoach ? base + doCoachExtra : base;
}

export const AVISO_REPETIR_CONFIRMAR = "Treinar mesmo assim";
