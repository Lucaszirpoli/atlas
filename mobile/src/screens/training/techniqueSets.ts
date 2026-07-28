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
  /** ativação (myo-reps/rest-pause) ou série principal (cluster/drop) */
  | "activation"
  /** mini-set clicável — no lugar do RIR mostra o campo BLOCO */
  | "block"
  /** queda de carga do drop-set / back-off */
  | "drop";

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

  if (tech.form === "activation_blocks") {
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
    linhas.push({ ...ultima, role: "activation", setType: st, blockIndex: 0, blockLabel: "Série principal", groupStart: true });
    const pesoBase = Number(peso.replace(",", "."));
    for (let i = 1; i <= tech.drops; i++) {
      const fator = Math.pow(1 - tech.dropPct / 100, i);
      const sugerido = Number.isFinite(pesoBase) && pesoBase > 0 ? String(Math.round(pesoBase * fator * 2) / 2) : "";
      linhas.push({
        ...base(),
        role: "drop",
        setType: st,
        blockIndex: i,
        blockLabel: `Queda ${i} · −${tech.dropPct}%`,
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
