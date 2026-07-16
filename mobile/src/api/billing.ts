import type { PurchasesPackage } from "react-native-purchases";

import { api } from "./client";
import { isEntitlementActive, isNativePurchasesAvailable, purchase, restore } from "./purchases";

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

/** Ativa o Pro. Em build nativo (dev client / produção) faz a compra real
 * via RevenueCat; o webhook do backend sincroniza o plano do usuário. No
 * Expo Go / web, usa a ativação de teste do backend (`/billing/dev-activate`)
 * pra validar o desbloqueio ponta a ponta sem precisar de build nativo. */
export async function subscribePro(pkg?: PurchasesPackage): Promise<{ plan: string; is_pro: boolean }> {
  if (isNativePurchasesAvailable() && pkg) {
    const info = await purchase(pkg);
    const active = isEntitlementActive(info);
    // Sincroniza o backend na hora (não depende do webhook) — o servidor
    // confirma o entitlement no RevenueCat e liga o Pro.
    await syncPlan(active).catch(() => {});
    return { plan: active ? "pro" : "free", is_pro: active };
  }
  const { data } = await api.post("/billing/dev-activate");
  return data;
}

/** Restaura compras já feitas (obrigatório pela Apple para apps com IAP). */
export async function restorePro(): Promise<{ plan: string; is_pro: boolean }> {
  const info = await restore();
  const active = isEntitlementActive(info);
  await syncPlan(active).catch(() => {});
  return { plan: active ? "pro" : "free", is_pro: active };
}

/** Pede ao backend pra confirmar o Pro direto no RevenueCat e ligar o plano.
 * Resolve quem comprou antes do webhook existir / quando o webhook falhou.
 * `isPro` é o que o SDK leu no cliente (fallback se o servidor não verificar).
 * Só LIGA o Pro — nunca rebaixa. */
export async function syncPlan(isPro?: boolean): Promise<{ plan: string; is_pro: boolean }> {
  const { data } = await api.post("/billing/sync", { is_pro: isPro });
  return data;
}

export async function cancelPro(): Promise<{ plan: string; is_pro: boolean }> {
  const { data } = await api.post("/billing/dev-deactivate");
  return data;
}
