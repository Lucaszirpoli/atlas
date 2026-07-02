import { api } from "./client";

export type WakeFeeling = "descansado" | "cansado" | "muito_cansado";

export type SleepLog = {
  id: number;
  sleep_at: string;
  wake_at: string;
  quality: number;
  wake_feeling: WakeFeeling;
  notes: string | null;
  duration_minutes: number;
};

export async function listSleepLogs(): Promise<SleepLog[]> {
  const { data } = await api.get<SleepLog[]>("/sleep");
  return data;
}

export async function logSleep(payload: {
  sleep_at: string;
  wake_at: string;
  quality: number;
  wake_feeling: WakeFeeling;
  notes?: string | null;
}): Promise<SleepLog> {
  const { data } = await api.post<SleepLog>("/sleep", payload);
  return data;
}
