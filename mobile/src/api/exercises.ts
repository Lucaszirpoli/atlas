import { api } from "./client";

export type MuscleGroup =
  | "chest"
  | "back"
  | "shoulders"
  | "biceps"
  | "triceps"
  | "quads"
  | "hamstrings"
  | "glutes"
  | "calves"
  | "abs"
  | "forearms"
  | "traps"
  | "full_body"
  | "cardio";

export type Equipment =
  | "barbell"
  | "dumbbell"
  | "machine"
  | "cable"
  | "bodyweight"
  | "kettlebell"
  | "band"
  | "smith_machine"
  | "other";

export type Difficulty = "beginner" | "intermediate" | "advanced";

export type Exercise = {
  id: number;
  name: string;
  primary_muscle_group: MuscleGroup;
  secondary_muscle_groups: string[];
  equipment: Equipment;
  difficulty: Difficulty;
  execution_text: string | null;
  video_url: string | null;
  is_custom: boolean;
};

export async function listExercises(filters?: {
  q?: string;
  muscle_group?: MuscleGroup;
  equipment?: Equipment;
}): Promise<Exercise[]> {
  const { data } = await api.get<Exercise[]>("/exercises", { params: filters });
  return data;
}

/** Cria um exercício próprio da pessoa (fica só pra ela: is_custom).
 *  O endpoint já existia no backend desde sempre e o app nunca chamava — a
 *  pessoa não tinha como cadastrar aquele aparelho específico da academia dela,
 *  nem dar nome ao que a importação de outro app não reconheceu. */
export async function createCustomExercise(payload: {
  name: string;
  primary_muscle_group: MuscleGroup;
  equipment: Equipment;
  secondary_muscle_groups?: string[];
  difficulty?: Difficulty;
  execution_text?: string | null;
}): Promise<Exercise> {
  const { data } = await api.post<Exercise>("/exercises", payload);
  return data;
}
