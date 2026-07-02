import { api } from "./client";

export type CalorieGoal = {
  id: number;
  mode: "manual" | "auto";
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
  sodium_mg: number | null;
  sugar_g: number | null;
  created_at: string;
};

export type CalorieGoalSuggestion = {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  current_goal: CalorieGoal | null;
  changed_significantly: boolean;
};

export async function getCurrentGoal(): Promise<CalorieGoal | null> {
  const { data } = await api.get<CalorieGoal | null>("/goals/calorie");
  return data;
}

export async function getAutoSuggestion(): Promise<CalorieGoalSuggestion> {
  const { data } = await api.get<CalorieGoalSuggestion>("/goals/calorie/suggestion");
  return data;
}

export async function applyAutoGoal(): Promise<CalorieGoal> {
  const { data } = await api.post<CalorieGoal>("/goals/calorie/auto");
  return data;
}

export async function applyManualGoal(payload: {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g?: number | null;
  sodium_mg?: number | null;
  sugar_g?: number | null;
}): Promise<CalorieGoal> {
  const { data } = await api.post<CalorieGoal>("/goals/calorie/manual", payload);
  return data;
}
