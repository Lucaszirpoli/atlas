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
};

export type Routine = {
  id: number;
  name: string;
  is_archived: boolean;
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
