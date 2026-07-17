import { api } from "./client";

// Chamadas que passam pela IA (Claude) podem levar bem mais que o timeout
// padrão de 15s do axios — gerar um treino/dieta com dica por item, ou uma
// resposta de chat, às vezes leva 20-40s. Sem isto, o app abortava e mostrava
// "não consegui gerar" mesmo com o backend respondendo. 90s é folga segura.
const AI_TIMEOUT_MS = 90000;

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
  const { data } = await api.post(
    "/ai/chat",
    { message, context_module: contextModule },
    { timeout: AI_TIMEOUT_MS }
  );
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

export type MethodPhase = {
  name: string;
  reps: string | null;
  sets: string | null;
  note: string | null;
};

/** Ficha completa de um método (tela de detalhe). O resumo da lista é o
 *  TrainingMethod acima; isto aqui só é buscado quando a pessoa abre um. */
export type TrainingMethodDetail = TrainingMethod & {
  progression_family: string | null;
  frequency_per_muscle: string | null;
  exercises_per_session: string | null;
  sets_per_exercise: string | null;
  reps: string | null;
  tempo: string | null;
  rest_seconds: string | null;
  rir: string | null;
  mesocycle_weeks: string | null;
  deload_rule: string | null;
  progression_rule: string | null;
  forbidden: string[];
  phases: MethodPhase[];
  /** Só os métodos desenhados pra atacar ponto fraco (Westside, Mountain Dog)
   *  oferecem a escolha — nos outros seria enfeite sem efeito no treino. */
  targets_weak_point: boolean;
};

export async function getTrainingMethodDetail(key: string): Promise<TrainingMethodDetail> {
  const { data } = await api.get<TrainingMethodDetail>(`/ai/training/methods/${key}`);
  return data;
}

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
  recommended?: boolean;
  recommended_reason?: string;
};

export async function getTrainingMethods(): Promise<TrainingMethod[]> {
  const { data } = await api.get<TrainingMethod[]>("/ai/training/methods");
  return data;
}

export async function generateTraining(payload: {
  method_key: string;
  available_days?: number | null;
  phase_index?: number;
  /** Grupo muscular a priorizar nos acessórios. Só tem efeito nos métodos com
   *  targets_weak_point; nos outros o backend ignora. */
  weak_point?: string | null;
}): Promise<GenerateTrainingResult> {
  const { data } = await api.post<GenerateTrainingResult>("/ai/training/generate", payload, {
    timeout: AI_TIMEOUT_MS,
  });
  return data;
}

/** "Monte um treino ideal pro seu perfil" — o backend escolhe o método que
 * melhor casa com experiência/objetivo/frequência da pessoa e gera o plano. */
export async function generatePersonalizedTraining(payload: {
  available_days?: number | null;
} = {}): Promise<GenerateTrainingResult> {
  const { data } = await api.post<GenerateTrainingResult>("/ai/training/personalized", payload, {
    timeout: AI_TIMEOUT_MS,
  });
  return data;
}

// --- IA de dieta: meta de macros com rails no código ----------------------

export type DietContext = {
  target_kcal: number | null;
  target_protein_g: number | null;
  target_carbs_g: number | null;
  target_fat_g: number | null;
  has_goal_defined: boolean;
  profile_restrictions: string[];
};

export type DietItem = {
  food_id: number;
  food_name: string;
  quantity_g: number;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
};

export type DietMeal = {
  category: string;
  items: DietItem[];
  note?: string | null;
};

export type DietPlan = {
  target: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
  meals: DietMeal[];
  totals: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
  restrictions: string[];
};

export type GenerateDietResult = {
  plan: DietPlan;
  intro: string | null;
  ai_used: boolean;
  is_faithful: boolean;
  violations: string[];
  ai_locked: boolean;
  free_credits_remaining?: number | null;
};

export async function getDietContext(): Promise<DietContext> {
  const { data } = await api.get<DietContext>("/ai/diet/context");
  return data;
}

export async function generateDiet(payload: {
  restrictions: string[];
  meals_per_day: number;
  variant?: number;
}): Promise<GenerateDietResult> {
  const { data } = await api.post<GenerateDietResult>("/ai/diet/generate", payload, {
    timeout: AI_TIMEOUT_MS,
  });
  return data;
}

export async function applyDiet(
  meals: { category: string; items: { food_id: number; quantity_g: number }[] }[]
): Promise<{ meals_logged: number; items_logged: number }> {
  const { data } = await api.post("/ai/diet/apply", { meals });
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
  const { data } = await api.post(
    "/ai/meal-photo",
    { image_base64: imageBase64, media_type: mediaType },
    { timeout: AI_TIMEOUT_MS }
  );
  return data;
}
