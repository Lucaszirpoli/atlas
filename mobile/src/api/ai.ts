import { api } from "./client";

export type ProposedAction = {
  tool:
    | "registrar_refeicao"
    | "atualizar_peso"
    | "ajustar_meta_calorica"
    | "criar_rotina_treino"
    | "criar_dieta_personalizada"
    | "criar_treino_personalizado";
  input: any;
};

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  proposed_action: ProposedAction | null;
  created_at: string;
};

export async function sendChatMessage(
  message: string,
  contextModule?: string
): Promise<{ reply: string; proposed_action: ProposedAction | null; free_credits_remaining: number | null }> {
  const { data } = await api.post("/ai/chat", { message, context_module: contextModule });
  return data;
}

export async function getChatHistory(): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>("/ai/chat/history");
  return data;
}

// --- Hub de IA: treino por metodologia (Arvo) ------------------------------

export type TrainingMethod = {
  key: string;
  name: string;
  author: string;
  goal: string;
  experience_min: string;
  days_per_week: number[];
  guide_excerpt: string;
};

export type PlanSlot = {
  order: number;
  muscle_group: string;
  is_compound: boolean;
  exercise_id: number | null;
  exercise_name: string;
  sets: string;
  reps: string;
  tempo: string | null;
  rest_seconds: string | null;
  rir: string | null;
  note: string | null;
};

export type PlanSession = {
  day_index: number;
  day_label: string;
  focus: string;
  phase_name: string | null;
  slots: PlanSlot[];
};

export type WorkoutPlan = {
  method_key: string;
  method_name: string;
  author: string;
  days_per_week: number;
  mesocycle: string | null;
  deload_rule: string | null;
  progression_rule: string;
  phase_context: string | null;
  sessions: PlanSession[];
  notes: string[];
};

export type GenerateTrainingResult = {
  plan: WorkoutPlan;
  intro: string | null;
  ai_used: boolean;
  is_faithful: boolean;
  violations: string[];
  ai_locked: boolean;
  free_credits_remaining?: number | null;
};

export async function getTrainingMethods(): Promise<TrainingMethod[]> {
  const { data } = await api.get<TrainingMethod[]>("/ai/training/methods");
  return data;
}

export async function generateTraining(payload: {
  method_key: string;
  available_days?: number | null;
  phase_index?: number;
}): Promise<GenerateTrainingResult> {
  const { data } = await api.post<GenerateTrainingResult>("/ai/training/generate", payload);
  return data;
}

export type MealPhotoItem = {
  nome_identificado: string;
  food_id: number | null;
  quantidade_estimada_g: number;
  confianca: "alta" | "media" | "baixa";
};

export async function analyzeMealPhoto(
  imageBase64: string,
  mediaType = "image/jpeg"
): Promise<{ itens: MealPhotoItem[]; aviso: string }> {
  const { data } = await api.post("/ai/meal-photo", {
    image_base64: imageBase64,
    media_type: mediaType,
  });
  return data;
}
