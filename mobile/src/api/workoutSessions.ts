import { api } from "./client";
import type { Exercise } from "./exercises";

export type SetType =
  | "warmup"
  | "straight"
  | "drop_set"
  | "rest_pause"
  | "myo_reps"
  | "cluster_set"
  | "to_failure"
  | "technical_failure"
  | "tempo"
  | "eccentric_emphasis"
  | "pre_exhaustion"
  | "superset"
  | "biset"
  | "triset"
  | "circuit";

export type WorkoutSession = {
  id: number;
  routine_id: number;
  started_at: string;
  completed_at: string | null;
};

export type ExercisePrefill = {
  exercise_id: number;
  last_performed_at: string | null;
  sets: { set_number: number; weight_kg: number; reps: number }[];
};

export type WorkoutSetLog = {
  id: number;
  exercise_id: number;
  exercise: Exercise;
  exercise_sort_order: number;
  set_number: number;
  weight_kg: number;
  reps: number;
  set_type: SetType;
  rpe: number | null;
  rir: number | null;
  completed_at: string;
};

export type WorkoutSessionDetail = WorkoutSession & { sets: WorkoutSetLog[] };

export type PersonalRecord = {
  exercise_id: number;
  exercise_name: string;
  weight_kg: number;
};

export type WorkoutSessionSummary = {
  session: WorkoutSessionDetail;
  total_volume_kg: number;
  duration_seconds: number;
  previous_session_volume_kg: number | null;
  volume_change_percent: number | null;
  prs: PersonalRecord[];
};

export async function startWorkoutSession(
  routineId: number
): Promise<{ session: WorkoutSession; prefill: ExercisePrefill[] }> {
  const { data } = await api.post("/workout-sessions", { routine_id: routineId });
  return data;
}

export async function logSet(
  sessionId: number,
  payload: {
    exercise_id: number;
    exercise_sort_order: number;
    set_number: number;
    weight_kg: number;
    reps: number;
    set_type?: SetType;
    rpe?: number | null;
    rir?: number | null;
  }
): Promise<WorkoutSetLog> {
  const { data } = await api.post<WorkoutSetLog>(`/workout-sessions/${sessionId}/sets`, payload);
  return data;
}

export async function completeWorkoutSession(sessionId: number): Promise<WorkoutSessionSummary> {
  const { data } = await api.post<WorkoutSessionSummary>(`/workout-sessions/${sessionId}/complete`);
  return data;
}

export async function listWorkoutSessions(routineId?: number): Promise<WorkoutSessionDetail[]> {
  const { data } = await api.get<WorkoutSessionDetail[]>("/workout-sessions", {
    params: routineId ? { routine_id: routineId } : undefined,
  });
  return data;
}
