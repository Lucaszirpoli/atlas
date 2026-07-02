import { api } from "./client";

export type PlateauEntry = {
  exercise_id: number;
  exercise_name: string;
  sessions_without_progress: number;
  current_weight_kg: number;
};

export type DeloadSuggestion = {
  consecutive_weeks_trained: number;
  suggested: boolean;
  message: string;
};

export async function getWorkoutInsights(): Promise<{
  plateaus: PlateauEntry[];
  deload: DeloadSuggestion;
}> {
  const { data } = await api.get("/workout-insights");
  return data;
}
