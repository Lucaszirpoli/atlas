import { api } from "./client";

export type CoachingSeverity = "info" | "attention" | "action";

export type CoachingFinding = {
  key: string;
  severity: CoachingSeverity;
  title: string;
  detail: string;
  proposal: string | null;
  // Presente só quando o ajuste é aplicável em 1 toque (ex.: { kcal_delta: -200 }).
  adjustment: { kcal_delta?: number } | null;
};

export type CoachingMetrics = {
  window_days: number;
  goal: string | null;
  weight_kg: number | null;
  weight_trend_kg_per_week: number | null;
  weight_pct_per_week: number | null;
  weight_points: number;
  avg_kcal: number | null;
  goal_kcal: number | null;
  avg_protein_g: number | null;
  protein_target_g: number | null;
  days_logged: number;
  sessions_per_week: number | null;
  avg_sleep_hours: number | null;
};

export type CoachingAnalysis = {
  window_days: number;
  goal: string | null;
  has_enough_data: boolean;
  confidence: "alta" | "parcial" | "baixa";
  headline: string;
  findings: CoachingFinding[];
  data_gaps: string[];
  metrics: CoachingMetrics;
};

/** Análise do Coaching no período (Pro). Determinística no backend — sem token.
 * windowDays: janela de análise (28/56/84 = 4/8/12 semanas). */
export async function getCoachingAnalysis(windowDays = 28): Promise<CoachingAnalysis> {
  const { data } = await api.get<CoachingAnalysis>("/coaching/analysis", {
    params: { window_days: windowDays },
  });
  return data;
}

export type ApplyDietResult = {
  applied: boolean;
  previous_kcal: number;
  new_kcal: number;
  kcal_delta: number;
  message: string;
};

/** Aplica o ajuste calórico de um achado — cria uma nova versão da meta. */
export async function applyDietAdjustment(findingKey: string): Promise<ApplyDietResult> {
  const { data } = await api.post<ApplyDietResult>("/coaching/apply/diet", { finding_key: findingKey });
  return data;
}

export type CoachingAdjustment = {
  id: number;
  finding_key: string;
  kind: string;
  kcal_delta: number;
  prev_kcal: number;
  new_kcal: number;
  created_at: string;
  reverted_at: string | null;
};

/** Histórico recente de ajustes aplicados (pra mostrar + oferecer Desfazer). */
export async function listCoachingAdjustments(): Promise<CoachingAdjustment[]> {
  const { data } = await api.get<CoachingAdjustment[]>("/coaching/adjustments");
  return data;
}

export type RevertResult = { reverted: boolean; restored_kcal: number; message: string };

/** Desfaz um ajuste: restaura a meta pro que era antes dele. */
export async function revertAdjustment(id: number): Promise<RevertResult> {
  const { data } = await api.post<RevertResult>(`/coaching/adjustments/${id}/revert`, {});
  return data;
}
