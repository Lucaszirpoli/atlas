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
  /** Dia (YYYY-MM-DD) a que a noite pertence, já calculado no fuso do
   * usuário pelo backend — é o dia em que ele ACORDOU, não em que deitou. */
  log_date: string;
};

export async function listSleepLogs(): Promise<SleepLog[]> {
  const { data } = await api.get<SleepLog[]>("/sleep");
  return data;
}

/** Mesmo mecanismo de `logWeight`/`logMeal` — ver api/weight.ts. */
function chaveDeRegistro(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function logSleep(payload: {
  sleep_at: string;
  wake_at: string;
  quality: number;
  wake_feeling: WakeFeeling;
  notes?: string | null;
}): Promise<SleepLog> {
  const { data } = await api.post<SleepLog>("/sleep", {
    ...payload,
    idempotency_key: chaveDeRegistro(),
  });
  return data;
}

export async function deleteSleepLog(id: number): Promise<void> {
  await api.delete(`/sleep/${id}`);
}
