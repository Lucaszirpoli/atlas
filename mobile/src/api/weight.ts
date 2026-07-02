import { api } from "./client";

export type WeightLog = {
  id: number;
  weight_kg: number;
  recorded_at: string;
};

export async function listWeightLogs(): Promise<WeightLog[]> {
  const { data } = await api.get<WeightLog[]>("/weight");
  return data;
}

export async function logWeight(weightKg: number): Promise<WeightLog> {
  const { data } = await api.post<WeightLog>("/weight", { weight_kg: weightKg });
  return data;
}
