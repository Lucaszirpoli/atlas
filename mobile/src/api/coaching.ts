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
  avg_carbs_g: number | null;
  goal_carbs_g: number | null;
  avg_fat_g: number | null;
  goal_fat_g: number | null;
  days_logged: number;
  sessions_per_week: number | null;
  volume_trend_pct: number | null;
  avg_sleep_hours: number | null;
  // Presente quando um marco de recomeço (troca de objetivo) recortou a janela.
  baseline_at: string | null;
};

export type CoachingChart = "peso" | "calorias" | "macros" | "sono" | "carga";

// Ajuste aplicável de uma barra. `kind` diz qual fluxo de aplicar chamar:
// dieta (kcal_delta, sem kind) | technique | progression | deload.
export type CoachingAdjustmentInfo = {
  kind?: "technique" | "progression" | "deload";
  kcal_delta?: number;
  technique?: string;
  technique_label?: string;
  exercise_id?: number;
  exercise_name?: string;
  new_weight?: number | null;
};

export type CoachingInsight = {
  key: string; // peso | calorias | macros | sono | carga | treino
  severity: CoachingSeverity;
  title: string;
  detail: string;
  chart: CoachingChart | null;
  finding_key: string | null;
  adjustment: CoachingAdjustmentInfo | null;
};

export type CoachingAnalysis = {
  window_days: number;
  goal: string | null;
  has_enough_data: boolean;
  confidence: "alta" | "parcial" | "baixa";
  headline: string;
  findings: CoachingFinding[];
  insights: CoachingInsight[];
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

export type ApplyTechniqueResult = {
  applied: boolean;
  exercise_name: string;
  technique_label: string;
  message: string;
};

/** Aplica uma técnica de intensidade ao exercício travado — vira uma dica do
 * coach na prévia do treino. O servidor rederiva a técnica (não confia no app). */
export async function applyTechnique(findingKey: string): Promise<ApplyTechniqueResult> {
  const { data } = await api.post<ApplyTechniqueResult>("/coaching/apply/technique", {
    finding_key: findingKey,
  });
  return data;
}

export type TechniqueCue = {
  id: number;
  exercise_id: number;
  exercise_name: string;
  technique: string;
  technique_label: string;
  cue_text: string;
  created_at: string;
};

/** Dicas de técnica ativas — a prévia do treino mostra em cima do exercício. */
export async function listTechniqueCues(): Promise<TechniqueCue[]> {
  const { data } = await api.get<TechniqueCue[]>("/coaching/technique-cues");
  return data;
}

export type RemoveCueResult = { removed: boolean; message: string };

/** Remove uma dica de técnica (o "desfazer" do lado do treino). */
export async function removeTechniqueCue(id: number): Promise<RemoveCueResult> {
  const { data } = await api.post<RemoveCueResult>(`/coaching/technique-cues/${id}/remove`, {});
  return data;
}

export type ResetBaselineResult = { reset: boolean; effective_from: string; message: string };

/** Recomeça a análise do coach a partir de agora (ao trocar de objetivo). Não
 * apaga histórico — só move o ponto de partida da leitura do coach. */
export async function resetCoachingBaseline(): Promise<ResetBaselineResult> {
  const { data } = await api.post<ResetBaselineResult>("/coaching/baseline/reset", {});
  return data;
}

export type ApplyActionResult = {
  applied: boolean;
  kind: string;
  title: string;
  message: string;
};

/** Aplica uma ação de treino do coach (progressão/deload/troca). O servidor
 * rederiva do estado atual — não confia no app. Reversível. */
export async function applyCoachAction(findingKey: string): Promise<ApplyActionResult> {
  const { data } = await api.post<ApplyActionResult>("/coaching/apply/action", { finding_key: findingKey });
  return data;
}

// Overlay ativo do coach no treino. exercise_id null = banner global (deload).
export type WorkoutOverlay = {
  source: "technique" | "action";
  id: number;
  kind: "technique" | "progression" | "exercise_swap" | "deload";
  exercise_id: number | null;
  exercise_name: string | null;
  title: string;
  detail: string;
  payload: { new_weight?: number | null; to_exercise_id?: number; to_name?: string };
};

/** Overlays ativos pro lado do treino (técnica + progressão/troca por exercício
 * + deload global). A prévia e a execução leem e mostram no exercício certo. */
export async function listWorkoutOverlays(): Promise<WorkoutOverlay[]> {
  const { data } = await api.get<WorkoutOverlay[]>("/coaching/overlays");
  return data;
}

/** Desfaz uma ação de treino (progressão/troca/deload). */
export async function revertCoachAction(id: number): Promise<{ removed: boolean; message: string }> {
  const { data } = await api.post(`/coaching/actions/${id}/revert`, {});
  return data;
}

// Item do painel unificado "O que o coach mudou".
export type CoachingChange = {
  source: "diet" | "technique" | "action";
  ref_id: number;
  icon: string;
  title: string;
  subtitle: string;
  created_at: string;
  active: boolean;
};

/** Feed unificado de tudo que o coach mudou (dieta + técnica + ações). */
export async function listCoachingChanges(): Promise<CoachingChange[]> {
  const { data } = await api.get<CoachingChange[]>("/coaching/changes");
  return data;
}

export type CheckinLine = { key: string; status: "good" | "warn" | "info"; text: string };
export type CoachingCheckin = {
  window_days: number;
  goal: string | null;
  has_data: boolean;
  headline: string;
  wins_count: number;
  lines: CheckinLine[];
};

/** Check-in semanal proativo — o resumo de segunda-feira do coach (7 dias). */
export async function getCoachingCheckin(): Promise<CoachingCheckin> {
  const { data } = await api.get<CoachingCheckin>("/coaching/checkin");
  return data;
}

export type CoachChatMessage = { role: "user" | "assistant"; content: string };

/** Pergunte ao coach. A IA responde ancorada na análise determinística. */
export async function coachChat(
  question: string,
  history: CoachChatMessage[]
): Promise<{ answer: string; used_ai: boolean }> {
  const { data } = await api.post<{ answer: string; used_ai: boolean }>("/coaching/chat", {
    question,
    history,
  });
  return data;
}
