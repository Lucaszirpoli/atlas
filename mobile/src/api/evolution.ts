import { api } from "./client";

export type WeightPoint = { date: string; weight_kg: number };
export type VolumePoint = { date: string; volume_kg: number; sets: number };
export type ExerciseOption = { id: number; name: string; set_count: number };
export type ExerciseProgressionPoint = { date: string; max_weight_kg: number; volume_kg: number };

export async function getWeightEvolution(): Promise<WeightPoint[]> {
  const { data } = await api.get<WeightPoint[]>("/evolution/weight");
  return data;
}

export async function getVolumeEvolution(): Promise<VolumePoint[]> {
  const { data } = await api.get<VolumePoint[]>("/evolution/volume");
  return data;
}

export async function getExercisesWithHistory(): Promise<ExerciseOption[]> {
  const { data } = await api.get<ExerciseOption[]>("/evolution/exercises");
  return data;
}

export async function getExerciseProgression(
  exerciseId: number
): Promise<{ exercise_name: string; points: ExerciseProgressionPoint[] }> {
  const { data } = await api.get(`/evolution/exercise/${exerciseId}`);
  return data;
}
