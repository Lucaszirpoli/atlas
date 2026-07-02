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
