import { api } from "./client";
import type { Exercise } from "./exercises";

export type SetType =
  | "warmup"
  | "straight"
  | "feeder"
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

export type WarmupFeederSet = {
  kind: "warmup" | "feeder";
  label: string;
  /** null na primeira vez no exercício (sem carga pra basear o peso). */
  weight_kg: number | null;
  reps_min: number;
  reps_max: number;
};

export type ExercisePrefill = {
  exercise_id: number;
  last_performed_at: string | null;
  sets: { set_number: number; weight_kg: number; reps: number }[];
  /** Nome do exercício de ORIGEM quando os números vieram de uma troca com
   * "manter registros" — a pessoa precisa saber de onde saiu a carga. */
  inherited_from_name?: string | null;
  /** Peso veio de "Aplicar mudança" do coach (progressão), ainda sem um
   * registro real — some sozinho assim que a pessoa registra de verdade. */
  suggested_by_coach?: boolean;
  /** RIR sugerido pra série de trabalho reta (a até-a-falha já é sempre RIR 0). */
  suggested_rir: number;
  /** Aquecimento + feeder — sempre as duas séries; sem histórico, weight_kg vem null. */
  warmup_feeder: WarmupFeederSet[];
};

/** Como um bloco de técnica avançada terminou. Nos mini-sets este campo
 * SUBSTITUI o RIR (spec §7.1): perguntar RIR de um bloco de 2 reps não diz
 * nada — o que importa é se fechou, fechou pela metade ou não saiu. */
export type BlockStatus = "completo" | "parcial" | "nao_concluido";

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
  /** 0 = ativação/série principal, 1..N = mini-sets. null = série reta. */
  block_index: number | null;
  block_status: BlockStatus | null;
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

/** Prévia do treino (pesos da última vez) SEM iniciar a sessão. */
export async function getWorkoutPreview(routineId: number): Promise<ExercisePrefill[]> {
  const { data } = await api.get<ExercisePrefill[]>("/workout-sessions/preview", {
    params: { routine_id: routineId },
  });
  return data;
}

export type ActiveWorkoutSession = {
  session: WorkoutSession;
  routine_id: number;
  routine_name: string;
  prefill: ExercisePrefill[];
  /** Quantas séries já foram registradas nesta sessão. */
  logged_sets: number;
};

/** O treino que ficou ABERTO no servidor (iniciado e nunca concluído), se
 * houver e se for recente. É o caminho de volta quando o app fecha sozinho:
 * as séries já registradas continuam lá, mas sem isto o app não tinha mais
 * como saber que aquele treino existia — ele sumia até do histórico, que só
 * lista treinos concluídos. */
export async function getActiveWorkoutSession(): Promise<ActiveWorkoutSession | null> {
  const { data } = await api.get<ActiveWorkoutSession | null>("/workout-sessions/active");
  return data ?? null;
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
    block_index?: number | null;
    block_status?: BlockStatus | null;
  }
): Promise<WorkoutSetLog> {
  const { data } = await api.post<WorkoutSetLog>(`/workout-sessions/${sessionId}/sets`, payload);
  return data;
}

export async function completeWorkoutSession(
  sessionId: number,
  durationMinutes?: number
): Promise<WorkoutSessionSummary> {
  const { data } = await api.post<WorkoutSessionSummary>(
    `/workout-sessions/${sessionId}/complete`,
    durationMinutes != null ? { duration_minutes: durationMinutes } : {}
  );
  return data;
}

/** Descarta a sessão (não vira histórico) — pra quando iniciou por engano. */
export async function discardWorkoutSession(sessionId: number): Promise<void> {
  await api.delete(`/workout-sessions/${sessionId}`);
}

/** Duração média (min) dos treinos concluídos. avg_minutes=null se pouco histórico. */
export async function getAvgWorkoutDuration(): Promise<{ avg_minutes: number | null; count: number }> {
  const { data } = await api.get("/workout-sessions/avg-duration");
  return data;
}

export async function listWorkoutSessions(routineId?: number): Promise<WorkoutSessionDetail[]> {
  const { data } = await api.get<WorkoutSessionDetail[]>("/workout-sessions", {
    params: routineId ? { routine_id: routineId } : undefined,
  });
  return data;
}

export async function getWorkoutSession(sessionId: number): Promise<WorkoutSessionDetail> {
  const { data } = await api.get<WorkoutSessionDetail>(`/workout-sessions/${sessionId}`);
  return data;
}

/** Corrige peso/reps de uma série já registrada (inclusive de um treino
 * passado) — pra quando a pessoa digitou errado na hora. */
export async function updateWorkoutSet(
  setId: number,
  payload: { weight_kg?: number; reps?: number }
): Promise<WorkoutSetLog> {
  const { data } = await api.patch<WorkoutSetLog>(`/workout-sessions/sets/${setId}`, payload);
  return data;
}
