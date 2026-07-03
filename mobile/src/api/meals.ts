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
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
  sodium_mg: number | null;
  sugar_g: number | null;
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
  items: { food_id: number; food: Food; quantity_g: number }[];
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

export async function logMeal(payload: {
  meal_category_id: number;
  logged_at: string;
  items: { food_id: number; quantity_g: number }[];
}): Promise<MealLog> {
  const { data } = await api.post<MealLog>("/meals", payload);
  return data;
}

export async function listMealsForDay(isoDate: string): Promise<MealLog[]> {
  const { data } = await api.get<MealLog[]>("/meals", { params: { day: isoDate } });
  return data;
}

export async function deleteMealLog(id: number): Promise<void> {
  await api.delete(`/meals/${id}`);
}

export async function listSavedMeals(): Promise<SavedMeal[]> {
  const { data } = await api.get<SavedMeal[]>("/meals/saved");
  return data;
}

export async function createSavedMeal(payload: {
  name: string;
  items: { food_id: number; quantity_g: number }[];
}): Promise<SavedMeal> {
  const { data } = await api.post<SavedMeal>("/meals/saved", payload);
  return data;
}
