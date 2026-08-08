import type { TechniqueForm, WorkoutOverlay } from "../../api/coaching";
import type { BlockStatus, SetType } from "../../api/workoutSessions";

/**
 * Técnica avançada prescrita -> SÉRIES DE VERDADE na execução (spec §7).
 *
 * A regra do produto é dura: quando o coach prescreve uma técnica, ela não pode
 * virar um aviso bonitinho em cima do exercício. Ela tem que aparecer nas
 * séries e nos campos que a pessoa preenche durante o treino — senão ninguém
 * executa a técnica, e a prescrição foi teatro.
 *
 * Este módulo é a tradução: pega a estrutura que veio do backend
 * (coaching/training_brain.TECHNIQUE_STRUCTURES) e devolve as linhas que a tela
 * de execução renderiza.
 */

/** Papel de cada linha na tela — decide qual interface a linha usa. */
export type SetRole =
  /** aquecimento/feeder (rampa de preparação) */
  | "prep"
  /** série de trabalho reta: peso, reps e RIR */
  | "work"
  /** ativação (myo-reps) ou série principal (cluster/drop/singles) */
  | "activation"
  /** mini-set clicável — no lugar do RIR mostra o campo BLOCO */
  | "block"
  /** queda de carga do back-off */
  | "drop"
  /** 1 repetição avulsa do rest-pause — feita ou não feita, sem status de bloco */
  | "single_rep";

export type SetRow = {
  weight: string;
  reps: string;
  completed: boolean;
  setType: SetType;
  rpe: string;
  rir: string;
  showMore: boolean;
  previous?: { weight_kg: number; reps: number };

  // --- técnica avançada ---------------------------------------------------
  role: SetRole;
  /** 0 = ativação/principal, 1..N = mini-sets. undefined em série reta. */
  blockIndex?: number;
  blockStatus?: BlockStatus;
  /** Rótulo da linha na tela ("Ativação", "Bloco 2", "Queda 1"). */
  blockLabel?: string;
  /** Reps fixas pelo método (myo-reps: 6 na ativação) — campo não editável. */
  repsLocked?: boolean;
  /** Descanso curto DENTRO da técnica, em segundos. */
  restAfterS?: number;
  /** Marca a primeira linha do grupo, pra desenhar o cabeçalho da técnica. */
  groupStart?: boolean;
  /** Marca a última linha do grupo, pra fechar o bloco visual. */
  groupEnd?: boolean;
  /** Série ADICIONADA pela pessoa ("+ série extra"), não prescrita pela
   * rotina — só estas podem ser removidas (e só antes de confirmadas). */
  manuallyAdded?: boolean;
  /** id do registro no servidor, devolvido ao confirmar a série. É o que
   * permite CORRIGIR peso/reps depois do ✓ (digitou errado e só percebeu na
   * série seguinte): sem ele, editar o campo mudava só o número na tela e o
   * histórico ficava com o valor errado, calado. */
  logId?: number;
  /** "pesoXreps" que o servidor tem guardado desta série. Serve pra não mandar
   * uma correção quando a pessoa só passou pelo campo sem mudar nada. */
  correcaoSalva?: string;
};

export type TechniquePrescription = {
  key: string;
  label: string;
  cue: string;
  form: TechniqueForm;
  activationReps: number;
  blocks: number;
  blockReps: number;
  firstRestS: number;
  restBetweenBlocksS: number;
  drops: number;
  dropPct: number;
  dropReps: number | null;
  restBeforeDropS: number;
};

/** Lê a técnica prescrita pra um exercício. null = nenhuma, ou uma técnica que
 * não muda a estrutura da série (superset é sobre emendar DOIS exercícios). */
export function prescriptionFor(
  overlays: WorkoutOverlay[],
  exerciseId: number
): TechniquePrescription | null {
  const o = overlays.find((x) => x.kind === "technique" && x.exercise_id === exerciseId);
  const form = o?.payload?.form;
  if (!o || !form || form === "cue_only") return null;
  const p = o.payload;
  return {
    key: p.technique ?? "",
    label: o.title,
    cue: o.detail,
    form,
    activationReps: p.activation_reps ?? 6,
    blocks: p.blocks ?? 3,
    blockReps: p.block_reps ?? 2,
    firstRestS: p.first_rest_s ?? p.rest_between_blocks_s ?? 20,
    restBetweenBlocksS: p.rest_between_blocks_s ?? 20,
    drops: p.drops ?? 2,
    dropPct: p.drop_pct ?? 25,
    dropReps: p.drop_reps ?? null,
    restBeforeDropS: p.rest_before_drop_s ?? 0,
  };
}

/** SetType a gravar pras linhas da técnica. Cai em "straight" pras técnicas
 * que não têm um membro próprio no enum (back-off, muscle round) — o que
 * identifica o bloco no histórico é o block_index, não o rótulo. */
function setTypeFor(key: string): SetType {
  const conhecidos: SetType[] = ["drop_set", "rest_pause", "myo_reps", "cluster_set"];
  return (conhecidos as string[]).includes(key) ? (key as SetType) : "straight";
}

function base(): Omit<SetRow, "role"> {
  return { weight: "", reps: "", completed: false, setType: "straight", rpe: "", rir: "", showMore: false };
}

/**
 * Expande a ÚLTIMA série de trabalho na estrutura da técnica.
 *
 * Por que só a última: é assim que essas técnicas são prescritas de verdade
 * ("na última série, ao falhar, tire 25%"). Aplicar drop-set em toda série
 * seria outra coisa — e uma que ninguém aguenta.
 */
export function expandTechnique(
  workRows: SetRow[],
  tech: TechniquePrescription,
  peso: string
): SetRow[] {
  if (workRows.length === 0) return workRows;
  const anteriores = workRows.slice(0, -1);
  const ultima = workRows[workRows.length - 1];
  const st = setTypeFor(tech.key);
  const linhas: SetRow[] = [];

  if (tech.form === "singles") {
    // Rest-pause: N repetições AVULSAS da MESMA carga, uma por vez — não é
    // bloco (bloco tem "quanto fechou": 2/2 reps, completo/parcial). Uma
    // repetição só tem feita ou não feita, então nenhuma linha aqui pede
    // status — o próprio toque de confirmar é o "feita".
    const total = tech.activationReps + tech.blocks * tech.blockReps;
    for (let i = 1; i <= total; i++) {
      linhas.push({
        ...(i === 1 ? ultima : base()),
        role: i === 1 ? "activation" : "single_rep",
        setType: st,
        blockIndex: i - 1,
        blockLabel: `R${i}`,
        weight: peso,
        reps: "1",
        repsLocked: true,
        restAfterS: tech.restBetweenBlocksS,
        groupStart: i === 1,
        groupEnd: i === total,
      });
    }
  } else if (tech.form === "activation_blocks") {
    linhas.push({
      ...ultima,
      role: "activation",
      setType: st,
      blockIndex: 0,
      blockLabel: "Ativação",
      reps: String(tech.activationReps),
      repsLocked: true,
      restAfterS: tech.firstRestS,
      groupStart: true,
      // Ativação é levada a 0 RIR — é o que dispara a técnica.
      rir: "0",
    });
    for (let i = 1; i <= tech.blocks; i++) {
      linhas.push({
        ...base(),
        role: "block",
        setType: st,
        blockIndex: i,
        blockLabel: `Bloco ${i}`,
        weight: peso,
        reps: String(tech.blockReps),
        restAfterS: tech.restBetweenBlocksS,
        groupEnd: i === tech.blocks,
      });
    }
  } else if (tech.form === "cluster") {
    linhas.push({
      ...ultima,
      role: "activation",
      setType: st,
      blockIndex: 0,
      blockLabel: `Série fragmentada · ${tech.blocks}×${tech.blockReps}`,
      reps: String(tech.blocks * tech.blockReps),
      repsLocked: true,
      groupStart: true,
    });
    for (let i = 1; i <= tech.blocks; i++) {
      linhas.push({
        ...base(),
        role: "block",
        setType: st,
        blockIndex: i,
        blockLabel: `Bloco ${i}`,
        weight: peso,
        reps: String(tech.blockReps),
        restAfterS: tech.restBetweenBlocksS,
        groupEnd: i === tech.blocks,
      });
    }
  } else if (tech.form === "drop") {
    // Hoje só o back-off usa esta forma (1 top set + N quedas encadeadas) — os
    // rótulos já nascem no vocabulário dele ("Top set" / "Back-off"), não um
    // "Série principal"/"Queda" genérico de quando drop-set também existia aqui.
    linhas.push({ ...ultima, role: "activation", setType: st, blockIndex: 0, blockLabel: "Top set", groupStart: true });
    const pesoBase = Number(peso.replace(",", "."));
    for (let i = 1; i <= tech.drops; i++) {
      const fator = Math.pow(1 - tech.dropPct / 100, i);
      const sugerido = Number.isFinite(pesoBase) && pesoBase > 0 ? String(Math.round(pesoBase * fator * 2) / 2) : "";
      const rotulo = tech.drops > 1 ? `Back-off ${i} · −${tech.dropPct}%` : `Back-off · −${tech.dropPct}%`;
      linhas.push({
        ...base(),
        role: "drop",
        setType: st,
        blockIndex: i,
        blockLabel: rotulo,
        weight: sugerido,
        reps: tech.dropReps ? String(tech.dropReps) : "",
        restAfterS: tech.restBeforeDropS,
        groupEnd: i === tech.drops,
      });
    }
  } else {
    return workRows;
  }

  return [...anteriores, ...linhas];
}

export const BLOCK_STATUS_LABEL: Record<BlockStatus, string> = {
  completo: "Completo",
  parcial: "Parcial",
  nao_concluido: "Não saiu",
};

/** Ciclo do toque no bloco: ainda não realizado → completo → parcial → não
 * saiu → volta pro não realizado. Um toque resolve o caso comum (completo). */
export const BLOCK_STATUS_CYCLE: (BlockStatus | undefined)[] = [
  undefined,
  "completo",
  "parcial",
  "nao_concluido",
];

export function nextBlockStatus(current: BlockStatus | undefined): BlockStatus | undefined {
  const i = BLOCK_STATUS_CYCLE.indexOf(current);
  return BLOCK_STATUS_CYCLE[(i + 1) % BLOCK_STATUS_CYCLE.length];
}

/** Como a tela de execução organiza as linhas pra desenhar: séries normais
 * ficam soltas ("single"), mas ativação + blocos/quedas de UMA técnica viram
 * UM item só ("technique") — é o que permite desenhar um cartão compacto com
 * chips B1/B2/B3 em vez de um cartão cheio por bloco (ajuste pós-v36, item 3:
 * "muita coisa na tela" era a queixa central). */
export type DisplayItem =
  | { kind: "single"; idx: number; row: SetRow }
  | { kind: "technique"; activationIdx: number; activation: SetRow; blocks: { idx: number; row: SetRow }[] };

export function buildDisplayItems(sets: SetRow[]): DisplayItem[] {
  const items: DisplayItem[] = [];
  let i = 0;
  while (i < sets.length) {
    const row = sets[i];
    if (row.role === "activation" && row.groupStart) {
      const blocks: { idx: number; row: SetRow }[] = [];
      let j = i + 1;
      while (j < sets.length && (sets[j].role === "block" || sets[j].role === "drop" || sets[j].role === "single_rep")) {
        blocks.push({ idx: j, row: sets[j] });
        const fechou = sets[j].groupEnd;
        j++;
        if (fechou) break;
      }
      items.push({ kind: "technique", activationIdx: i, activation: row, blocks });
      i = j;
    } else {
      items.push({ kind: "single", idx: i, row });
      i++;
    }
  }
  return items;
}
