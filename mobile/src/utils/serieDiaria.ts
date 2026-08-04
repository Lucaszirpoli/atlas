/** Séries de gráfico com UM ponto por dia, sem buracos.
 *
 * O problema que isto resolve: o gráfico só tinha ponto nos dias em que a
 * pessoa registrou algo. Quem pesou 70 kg no dia 31 e voltou a pesar 74 kg no
 * dia 2 via uma linha entre dois pontos soltos — o dia 1, em que ela
 * simplesmente não subiu na balança, sumia do eixo. A linha ficava curta e
 * mentia sobre o tempo decorrido.
 *
 * A regra pedida é a de "último valor conhecido": o dia sem registro herda o
 * valor do dia anterior, e a série vai até HOJE. O peso do dia 1 é 70 kg
 * porque ela continuava pesando 70 kg — só não mediu.
 *
 * O que isto NÃO faz, de propósito: mexer nas médias, na adesão ou na
 * sequência. Isto é camada de DESENHO. Média de calorias, "dias registrados" e
 * o recorde continuam contando só os dias reais — repetir a última refeição
 * registrada em três dias sem registro inventaria comida que ninguém comeu.
 */

/** Data local (não UTC) de um instante ou de uma data "YYYY-MM-DD".
 *
 * `new Date("2026-08-04")` é interpretado pelo JS como MEIA-NOITE EM UTC, que
 * no Brasil (UTC-3) cai às 21h do dia 3 — era isso que fazia o app rotular o
 * ponto de terça como segunda. Data pura é lida campo a campo; instante com
 * hora (ISO com T) é convertido normalmente. */
export function diaLocal(valor: string | number | Date): Date {
  if (typeof valor === "string") {
    const soData = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor);
    if (soData) {
      return new Date(Number(soData[1]), Number(soData[2]) - 1, Number(soData[3]));
    }
  }
  const d = new Date(valor);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Timestamp da meia-noite local do dia daquele valor — a coordenada X que
 * todos os gráficos usam. */
export function tsDoDia(valor: string | number | Date): number {
  return diaLocal(valor).getTime();
}

const UM_DIA = 86400000;

/** `real: true` só no dia em que a pessoa de fato registrou algo — os dias
 * herdados (último valor conhecido) vêm com `real: false`, pra quem desenha
 * o gráfico saber onde NÃO desenhar uma bolinha (herança não é um evento). */
export type PontoDiario = { x: number; y: number; real?: boolean };

/** Ordena por dia, resolve empates (dois registros no mesmo dia → vale o
 * último) e preenche os dias vagos com o último valor conhecido.
 *
 * `ate` é o fim da linha (padrão: hoje). `desde` opcional puxa o início para
 * trás — útil quando o gráfico tem um período fixo de 30 dias mas o primeiro
 * registro é mais recente que isso (aí a linha começa no primeiro registro,
 * não numa reta inventada antes dele). */
export function serieDiaria(
  pontos: PontoDiario[],
  opcoes: { ate?: number; maxDias?: number } = {}
): PontoDiario[] {
  if (pontos.length === 0) return [];

  // Um valor por dia: o último registro do dia é o que vale (foi o mais
  // recente que ela informou).
  const porDia = new Map<number, number>();
  for (const p of [...pontos].sort((a, b) => a.x - b.x)) {
    porDia.set(tsDoDia(p.x), p.y);
  }

  const diasComRegistro = [...porDia.keys()].sort((a, b) => a - b);
  const primeiro = diasComRegistro[0];
  const fim = Math.max(tsDoDia(opcoes.ate ?? Date.now()), diasComRegistro[diasComRegistro.length - 1]);

  // Trava de segurança: sem ela, um registro antigo e esquecido geraria
  // milhares de pontos e travaria o desenho.
  const maxDias = opcoes.maxDias ?? 400;
  const inicio = Math.max(primeiro, fim - (maxDias - 1) * UM_DIA);

  const saida: PontoDiario[] = [];
  let ultimo: number | null = null;
  for (const dia of diasComRegistro) {
    if (dia <= inicio) ultimo = porDia.get(dia)!;
  }
  for (let dia = inicio; dia <= fim; dia += UM_DIA) {
    const valor = porDia.get(dia);
    const real = valor !== undefined;
    if (real) ultimo = valor;
    if (ultimo !== null) saida.push({ x: dia, y: ultimo, real });
  }
  return saida;
}

/** Mesma coisa para as séries que vêm com a data em campo separado. */
export function serieDiariaDe<T>(
  itens: T[],
  data: (item: T) => string | number | Date,
  valor: (item: T) => number,
  opcoes?: { ate?: number; maxDias?: number }
): PontoDiario[] {
  return serieDiaria(
    itens.map((i) => ({ x: tsDoDia(data(i)), y: valor(i) })),
    opcoes
  );
}
