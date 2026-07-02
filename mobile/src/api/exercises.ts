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
