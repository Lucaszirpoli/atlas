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

/** Apaga UM registro de peso. Serve pro erro de digitação (78 virou 7,8) —
 * sem isto, um número errado ficava pra sempre distorcendo o gráfico e a
 * tendência que o coach lê. */
export async function deleteWeightLog(id: number): Promise<void> {
  await api.delete(`/weight/${id}`);
}
