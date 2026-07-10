import { api } from "./client";

export type DietContext = {
  goal: string | null;
  weight_kg: number | null;
  height_cm: number | null;
  imc: number | null;
  imc_label: string | null;
  target_kcal: number;
  target_protein_g: number | null;
  has_goal_defined: boolean;
};

export type DietTemplateSummary = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  goals: string[];
  scaled_kcal: number;
  scaled_protein_g: number;
};

export type DietTemplateItem = {
  food_id: number;
  food_name: string;
  quantity_g: number;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
};

export type DietTemplateMeal = { category: string; items: DietTemplateItem[] };

export type DietTemplatePreview = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  goals: string[];
  meals: DietTemplateMeal[];
  totals: { kcal: number; protein_g: number; carbs_g: number; fat_g: number };
  context: DietContext;
};

/** Dietas semi-prontas (curadas, sem IA), já escaladas pra meta da pessoa. */
export async function listDietTemplates(): Promise<{ context: DietContext; templates: DietTemplateSummary[] }> {
  const { data } = await api.get("/diet-templates");
  return data;
}

export async function previewDietTemplate(id: string): Promise<DietTemplatePreview> {
  const { data } = await api.get(`/diet-templates/${id}/preview`);
  return data;
}

export async function applyDietTemplate(
  id: string
): Promise<{ template_name: string; meals_logged: number; items_logged: number; totals: DietTemplatePreview["totals"] }> {
  const { data } = await api.post(`/diet-templates/${id}/apply`);
  return data;
}
