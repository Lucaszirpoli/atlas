import { api } from "./client";

export type BiologicalSex = "male" | "female";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type Goal = "emagrecimento" | "hipertrofia" | "manutencao" | "performance" | "recomposicao";

export type ProfileCalc = {
  biological_sex: BiologicalSex;
  age: number;
  height_cm: number;
  activity_level: ActivityLevel;
  goal: Goal;
  current_weight_kg: number | null;
};

export type ProfileCalcUpdate = Partial<ProfileCalc>;

export async function getProfileCalc(): Promise<ProfileCalc> {
  const { data } = await api.get<ProfileCalc>("/users/profile/calc");
  return data;
}

export async function updateProfileCalc(payload: ProfileCalcUpdate): Promise<ProfileCalc> {
  const { data } = await api.patch<ProfileCalc>("/users/profile/calc", payload);
  return data;
}

/** Fuso do aparelho ("America/Sao_Paulo"). É o que diz ao backend QUE DIA de
 * calendário é cada registro — sem isso ele fatiava o dia em UTC e tudo que
 * era registrado depois das 21h caía no dia seguinte. Silencioso de propósito:
 * é um detalhe de infraestrutura, nunca deve atrapalhar quem está usando. */
export async function reportDeviceTimezone(): Promise<void> {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!tz) return;
    await api.put("/users/timezone", { timezone: tz });
  } catch {
    // sem rede / fuso desconhecido: o backend usa o padrão do produto
  }
}
