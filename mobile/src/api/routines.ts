import { api } from "./client";
import type { Exercise } from "./exercises";

export type RoutineExercise = {
  id: number;
  exercise_id: number;
  exercise: Exercise;
  sort_order: number;
  target_sets: number;
  target_reps_min: number;
  target_reps_max: number | null;
  rest_seconds: number;
  notes: string | null;
  // Intenção de cada série de trabalho: "to_failure" | null (série reta
  // normal, sem opinião). Tamanho = target_sets. Aquecimento/feeder não
  // entram aqui — vêm calculados em ExercisePrefill.warmup_feeder. O coach
  // preenche isto ao montar a rotina; rotina manual vem com tudo null.
  set_intents: (string | null)[];
};

export type Routine = {
  id: number;
  name: string;
  is_archived: boolean;
  /** Quem montou: "coach" = o motor do Coaching (prescrição fechada na
   * execução — sem "mais opções", sem série extra, aquecimento/feeder fixos);
   * "manual" = a pessoa montou, importou ou pediu no chat, e manda em tudo. */
  origem: "coach" | "manual";
  exercises: RoutineExercise[];
  created_at: string;
};

export type RoutineExerciseInput = {
  exercise_id: number;
  target_sets: number;
  target_reps_min: number;
  target_reps_max?: number | null;
  rest_seconds?: number;
  notes?: string | null;
};

export async function listRoutines(includeArchived = false): Promise<Routine[]> {
  const { data } = await api.get<Routine[]>("/routines", {
    params: { include_archived: includeArchived },
  });
  return data;
}

export async function getRoutine(id: number): Promise<Routine> {
  const { data } = await api.get<Routine>(`/routines/${id}`);
  return data;
}

export async function createRoutine(payload: {
  name: string;
  exercises: RoutineExerciseInput[];
}): Promise<Routine> {
  const { data } = await api.post<Routine>("/routines", payload);
  return data;
}

export async function updateRoutine(
  id: number,
  payload: { name: string; exercises: RoutineExerciseInput[] }
): Promise<Routine> {
  const { data } = await api.put<Routine>(`/routines/${id}`, payload);
  return data;
}

export async function deleteRoutine(id: number): Promise<void> {
  await api.delete(`/routines/${id}`);
}

export async function archiveRoutine(id: number): Promise<Routine> {
  const { data } = await api.post<Routine>(`/routines/${id}/archive`);
  return data;
}

export async function unarchiveRoutine(id: number): Promise<Routine> {
  const { data } = await api.post<Routine>(`/routines/${id}/unarchive`);
  return data;
}

export async function duplicateRoutine(id: number): Promise<Routine> {
  const { data } = await api.post<Routine>(`/routines/${id}/duplicate`);
  return data;
}

export type SwapExerciseResult = {
  exercicio_anterior: string;
  exercicio_novo: string;
  /** Por que ESTE substituto, em uma frase — o coach explicando a escolha. */
  motivo: string;
  routine: Routine;
};

/** Pede pro coach trocar UM exercício da rotina. Quem escolhe o substituto é o
 * servidor, pelas mesmas regras da montagem (mesmo músculo e papel, tier,
 * preferências, sem repetir o que já está no treino) — o app não manda opção
 * nenhuma, só diz qual vaga a pessoa não quer. Séries e reps ficam como estavam. */
export async function swapRoutineExercise(
  routineId: number,
  routineExerciseId: number
): Promise<SwapExerciseResult> {
  const { data } = await api.post<SwapExerciseResult>(
    `/routines/${routineId}/exercises/${routineExerciseId}/swap`
  );
  return data;
}

/** Cria várias rotinas de uma vez (o treino que a IA montou), opcionalmente
 * arquivando as ativas antes. Uma chamada só e atômica — antes o app fazia N
 * chamadas soltas e qualquer falha deixava o treino pela metade. Exercícios
 * que a IA errou o id voltam em `skipped_exercises` em vez de derrubar tudo. */
export type ImportedExercise = {
  nome_original: string;
  exercise_id: number | null;
  exercise_nome: string | null;
  confianca: number;
  /** true = casou com pouca certeza (ou nem casou): a tela pede conferência. */
  revisar: boolean;
  series: number;
  reps_min: number;
  reps_max: number | null;
};

export type ImportedRoutine = { nome: string; exercicios: ImportedExercise[] };

export type ImportPreview = {
  rotinas: ImportedRoutine[];
  total_exercicios: number;
  casados: number;
  para_revisar: number;
  sem_par: number;
};

/** Lê o CSV exportado de outro app (Hevy, Strong, Jefit) e PROPÕE as rotinas.
 *  Não grava — quem grava é o createRoutinesBulk, depois da sua conferência. */
export async function previewRoutineImport(csvContent: string): Promise<ImportPreview> {
  const { data } = await api.post<ImportPreview>("/routines/import/preview", {
    csv_content: csvContent,
  });
  return data;
}

export async function createRoutinesBulk(payload: {
  rotinas: {
    nome: string;
    exercicios: {
      exercise_id: number;
      target_sets?: number;
      target_reps_min?: number;
      target_reps_max?: number | null;
      rest_seconds?: number;
      notes?: string | null;
    }[];
  }[];
  substituir_existentes?: boolean;
}): Promise<{ created: number; archived: number; skipped_exercises: number[] }> {
  const { data } = await api.post("/routines/bulk", payload, { timeout: 60000 });
  return data;
}
