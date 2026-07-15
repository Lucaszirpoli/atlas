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
