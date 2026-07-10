import { api } from "./client";

/** Assistente determinístico (sem IA/token). Responde sobre os dados do
 * usuário e conhecimento fitness. */
export async function askAssistant(text: string): Promise<{ reply: string; answered: boolean }> {
  const { data } = await api.post("/assistant/ask", { text });
  return data;
}
