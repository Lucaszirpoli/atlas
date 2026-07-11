import { api } from "./client";

export type Offering = {
  price_brl: number;
  period: string;
  benefits: string[];
  provider_ready: boolean; // RevenueCat configurado no servidor?
  dev_mode: boolean; // ativação de teste liberada?
};

export async function getOffering(): Promise<Offering> {
  const { data } = await api.get<Offering>("/billing/offering");
  return data;
}

/** Ativa o Pro. Em produção (build nativo com RevenueCat) isto seria feito
 * pela compra in-app; enquanto o provedor não está plugado, usa a ativação de
 * teste do backend pra validar o desbloqueio ponta a ponta. */
export async function subscribePro(): Promise<{ plan: string; is_pro: boolean }> {
  const { data } = await api.post("/billing/dev-activate");
  return data;
}

export async function cancelPro(): Promise<{ plan: string; is_pro: boolean }> {
  const { data } = await api.post("/billing/dev-deactivate");
  return data;
}
