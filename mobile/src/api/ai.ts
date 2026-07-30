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

