import { api } from "./client";
import type { Food } from "./foods";

export type MealCategory = {
  id: number;
  name: string;
  sort_order: number;
};

export type MealLogItem = {
  id: number;
  food_id: number;
  food: Food;
  quantity_g: number;
  unit_label: string | null;
  unit_amount: number | null;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
  sodium_mg: number | null;
  sugar_g: number | null;
};

/** Item na hora de registrar. As gramas são obrigatórias (base do cálculo);
 * unit_label/unit_amount são opcionais e só vão quando a pessoa escolheu por
 * medida caseira ("2 fatias"), pra guardar/mostrar assim. */
export type MealItemInput = {
  food_id: number;
  quantity_g: number;
  unit_label?: string | null;
  unit_amount?: number | null;
};

export type MealLog = {
  id: number;
  meal_category_id: number;
  logged_at: string;
  items: MealLogItem[];
};

export type SavedMeal = {
  id: number;
  name: string;
  items: {
    food_id: number;
    food: Food;
    quantity_g: number;
    unit_label: string | null;
    unit_amount: number | null;
  }[];
};

export async function listMealCategories(): Promise<MealCategory[]> {
  const { data } = await api.get<MealCategory[]>("/meals/categories");
  return data;
}

export async function createMealCategory(name: string): Promise<MealCategory> {
  const { data } = await api.post<MealCategory>("/meals/categories", { name });
  return data;
}

export async function renameMealCategory(id: number, name: string): Promise<MealCategory> {
  const { data } = await api.patch<MealCategory>(`/meals/categories/${id}`, { name });
  return data;
}

export async function deleteMealCategory(id: number): Promise<void> {
  await api.delete(`/meals/categories/${id}`);
}

/** Chave de UMA tentativa de registro. Vai junto no corpo do POST, então o
 * retry automático do axios (rede que cai depois de o servidor já ter gravado)
 * reenvia a MESMA chave — e o backend devolve o registro que já existe em vez
 * de criar outro. É o conserto do "às vezes o alimento salva duas vezes". */
function chaveDeRegistro(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export async function logMeal(payload: {
  meal_category_id: number;
  logged_at: string;
  items: MealItemInput[];
}): Promise<MealLog> {
  const { data } = await api.post<MealLog>("/meals", {
    ...payload,
    idempotency_key: chaveDeRegistro(),
  });
  return data;
}

export type ParsedMealItem = {
  raw: string;
  food: Food | null;
  alternatives: Food[];
  quantity_g: number | null;
  status: "ok" | "porcao_estimada" | "sem_alimento" | "nao_encontrado";
};

/** Interpreta um texto ("30g de requeijão, 2 ovos") em itens revisáveis.
 * Determinístico no backend — sem IA/token. */
export async function parseMeal(text: string): Promise<ParsedMealItem[]> {
  const { data } = await api.post<ParsedMealItem[]>("/meals/parse", { text });
  return data;
}

export async function listMealsForDay(isoDate: string): Promise<MealLog[]> {
  const { data } = await api.get<MealLog[]>("/meals", { params: { day: isoDate } });
  return data;
}

/** Corrige a quantidade de um item já registrado (toque no alimento no diário).
 * O backend reconta kcal/macros. As gramas são a base; unit_label/unit_amount
 * acompanham quando a pessoa editou por medida caseira. */
export async function updateMealItem(
  itemId: number,
  payload: { quantity_g: number; unit_label?: string | null; unit_amount?: number | null }
): Promise<MealLogItem> {
  const { data } = await api.patch<MealLogItem>(`/meals/items/${itemId}`, payload);
  return data;
}

export async function deleteMealLog(id: number): Promise<void> {
  await api.delete(`/meals/${id}`);
}

/** Apaga UM alimento do diário, sem mexer nos outros da mesma refeição.
 * Diferente de `deleteMealLog`, que apaga o registro inteiro. */
export async function deleteMealItem(itemId: number): Promise<void> {
  await api.delete(`/meals/items/${itemId}`);
}

/** Veredito do sistema sobre um dia alimentar: dá pra usar nas médias ou o
 * registro ficou pela metade? (spec §10.2/§10.3) */
export type NutritionDay = {
  day: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  meals: number;
  quality: "completo" | "confirmar" | "provavelmente_incompleto";
  /** Decisão da pessoa; null = ainda no automático. */
  mark: "confirmed" | "incomplete" | null;
  valid_for_average: boolean;
  needs_attention: boolean;
};

export async function listNutritionDays(days = 30): Promise<NutritionDay[]> {
  const { data } = await api.get<NutritionDay[]>("/meals/days", { params: { days } });
  return data;
}

/** "Aceitar como está" (confirmed), "marcar como incompleto" (incomplete) ou
 * voltar pro automático (null). Nunca apaga registro — só muda se o dia entra
 * nas médias. */
export async function markNutritionDay(
  isoDate: string,
  status: "confirmed" | "incomplete" | null
): Promise<void> {
  await api.put(`/meals/days/${isoDate}/mark`, { status });
}

export async function listSavedMeals(): Promise<SavedMeal[]> {
  const { data } = await api.get<SavedMeal[]>("/meals/saved");
  return data;
}

export async function createSavedMeal(payload: {
  name: string;
  items: MealItemInput[];
}): Promise<SavedMeal> {
  const { data } = await api.post<SavedMeal>("/meals/saved", payload);
  return data;
}
