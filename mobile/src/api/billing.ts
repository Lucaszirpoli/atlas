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
    return { plan: isEntitlementActive(info) ? "pro" : "free", is_pro: isEntitlementActive(info) };
  }
  const { data } = await api.post("/billing/dev-activate");
  return data;
}

/** Restaura compras já feitas (obrigatório pela Apple para apps com IAP). */
export async function restorePro(): Promise<{ plan: string; is_pro: boolean }> {
  const info = await restore();
  return { plan: isEntitlementActive(info) ? "pro" : "free", is_pro: isEntitlementActive(info) };
}

export async function cancelPro(): Promise<{ plan: string; is_pro: boolean }> {
  const { data } = await api.post("/billing/dev-deactivate");
  return data;
}
