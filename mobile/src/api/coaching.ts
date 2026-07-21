import { api } from "./client";

export type CoachingSeverity = "info" | "attention" | "action";

export type CoachingFinding = {
  key: string;
  severity: CoachingSeverity;
  title: string;
  detail: string;
  proposal: string | null;
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

/** Análise semanal do Coaching (Pro). Determinística no backend — sem token. */
export async function getCoachingAnalysis(): Promise<CoachingAnalysis> {
  const { data } = await api.get<CoachingAnalysis>("/coaching/analysis");
  return data;
}
