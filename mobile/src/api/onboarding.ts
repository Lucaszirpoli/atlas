import { api } from "./client";

export type OnboardingPayload = {
  biological_sex: "male" | "female";
  age: number;
  height_cm: number;
  current_weight_kg: number;
  activity_level: "sedentary" | "light" | "moderate" | "active" | "very_active";
  goal: "emagrecimento" | "hipertrofia" | "manutencao" | "performance" | "recomposicao";
  experience_level: "iniciante" | "intermediario" | "avancado";
  training_location:
    | "academia_completa"
    | "academia_basica"
    | "casa_com_equipamento"
    | "casa_sem_equipamento";
  training_style_preference: "curto_intenso" | "longo_volumoso" | "ia_decide";
  available_days: string[];
  dietary_restrictions: string[];
  injuries_limitations: string | null;
  preferred_advanced_technique: string | null;
  trains_with_partner: boolean;
  partner_handle: string | null;
  accepted_lgpd_health_data: boolean;
  accepted_medical_disclaimer: boolean;
};

export async function submitOnboarding(
  payload: OnboardingPayload
): Promise<{ onboarding_completed: boolean }> {
  const { data } = await api.post("/users/onboarding", payload);
  return data;
}
