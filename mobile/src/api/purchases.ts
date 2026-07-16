import Constants from "expo-constants";
import { Platform } from "react-native";
import Purchases, { type CustomerInfo, type PurchasesOffering, type PurchasesPackage } from "react-native-purchases";

/** Identificador do entitlement configurado no dashboard do RevenueCat. */
export const PRO_ENTITLEMENT_ID = "pro";

/** Expo Go e a versão web não carregam módulos nativos — nesses casos o SDK
 * real do RevenueCat não está disponível, e o app cai no fallback de dev
 * (`/billing/dev-activate`) já existente em `billing.ts`. Só funciona em
 * dev client / build nativo (EAS build). */
export function isNativePurchasesAvailable(): boolean {
  return Platform.OS !== "web" && Constants.appOwnership !== "expo";
}

let configured = false;

export function configurePurchases(appUserId: string) {
  if (!isNativePurchasesAvailable() || configured) return;

  const apiKey =
    Platform.OS === "ios"
      ? process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY
      : process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY;

  if (!apiKey) return;

  Purchases.configure({ apiKey, appUserID: appUserId });
  configured = true;
}

export async function getCurrentOffering(): Promise<PurchasesOffering | null> {
  const offerings = await Purchases.getOfferings();
  return offerings.current;
}

export async function purchase(pkg: PurchasesPackage): Promise<CustomerInfo> {
  const { customerInfo } = await Purchases.purchasePackage(pkg);
  return customerInfo;
}

export async function restore(): Promise<CustomerInfo> {
  return Purchases.restorePurchases();
}

export function isEntitlementActive(info: CustomerInfo): boolean {
  return info.entitlements.active[PRO_ENTITLEMENT_ID] != null;
}

/** Lê o entitlement 'pro' atual da loja (sem forçar compra). null se o SDK
 * nativo não está disponível ou falhou. Usado na inicialização pra sincronizar
 * quem já é Pro. */
export async function getEntitlementActive(): Promise<boolean | null> {
  if (!isNativePurchasesAvailable()) return null;
  try {
    const info = await Purchases.getCustomerInfo();
    return isEntitlementActive(info);
  } catch {
    return null;
  }
}
