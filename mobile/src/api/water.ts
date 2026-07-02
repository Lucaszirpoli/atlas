import { api } from "./client";

export type WaterLog = {
  id: number;
  amount_ml: number;
  logged_at: string;
};

export type WaterSummary = {
  goal_ml: number;
  total_ml_today: number;
  logs_today: WaterLog[];
};

export async function getTodayWaterSummary(): Promise<WaterSummary> {
  const { data } = await api.get<WaterSummary>("/water/today");
  return data;
}

export async function logWater(amountMl: number): Promise<WaterLog> {
  const { data } = await api.post<WaterLog>("/water", { amount_ml: amountMl });
  return data;
}
