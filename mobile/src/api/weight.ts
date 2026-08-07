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

/** Chave de UMA tentativa de registro — mesmo mecanismo de `logMeal` (ver
 * api/meals.ts). Sem ela, o retry automático do axios numa rede ruim (resposta
 * perdida depois de o servidor já ter gravado) reenviava o POST e o peso
 * entrava duplicado no histórico. */
function chaveDeRegistro(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function logWeight(weightKg: number): Promise<WeightLog> {
  const { data } = await api.post<WeightLog>("/weight", {
    weight_kg: weightKg,
    idempotency_key: chaveDeRegistro(),
  });
  return data;
}

/** Apaga UM registro de peso. Serve pro erro de digitação (78 virou 7,8) —
 * sem isto, um número errado ficava pra sempre distorcendo o gráfico e a
 * tendência que o coach lê. */
export async function deleteWeightLog(id: number): Promise<void> {
  await api.delete(`/weight/${id}`);
}
