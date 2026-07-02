import { api } from "./client";

export type ProposedAction = {
  tool: "registrar_refeicao" | "atualizar_peso" | "ajustar_meta_calorica" | "criar_rotina_treino";
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
): Promise<{ reply: string; proposed_action: ProposedAction | null }> {
  const { data } = await api.post("/ai/chat", { message, context_module: contextModule });
  return data;
}

export async function getChatHistory(): Promise<ChatMessage[]> {
  const { data } = await api.get<ChatMessage[]>("/ai/chat/history");
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
