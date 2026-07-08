import { api } from "./client";

export type Food = {
  id: number;
  source: "taco" | "open_food_facts" | "custom";
  barcode: string | null;
  name: string;
  brand: string | null;
  kcal_per_100g: number;
  protein_g_per_100g: number;
  carbs_g_per_100g: number;
  fat_g_per_100g: number;
  fiber_g_per_100g: number | null;
  sodium_mg_per_100g: number | null;
  sugar_g_per_100g: number | null;
  default_portion_g: number;
  default_portion_label: string | null;
};

export async function searchFoods(query: string): Promise<Food[]> {
  const { data } = await api.get<Food[]>("/foods/search", { params: { q: query } });
  return data;
}

/** Busca de marcas ao vivo (Open Food Facts) — mais lenta, chamada em separado
 * pra não travar a digitação. O app mostra o local na hora e encaixa isto. */
export async function searchFoodBrands(query: string): Promise<Food[]> {
  const { data } = await api.get<Food[]>("/foods/search/brands", { params: { q: query } });
  return data;
}

export async function getFoodByBarcode(barcode: string): Promise<Food | null> {
  try {
    const { data } = await api.get<Food>(`/foods/barcode/${barcode}`);
    return data;
  } catch (err: any) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
}

export async function createCustomFood(payload: {
  name: string;
  brand?: string | null;
  kcal_per_100g: number;
  protein_g_per_100g: number;
  carbs_g_per_100g: number;
  fat_g_per_100g: number;
  fiber_g_per_100g?: number | null;
  sodium_mg_per_100g?: number | null;
  sugar_g_per_100g?: number | null;
  default_portion_g?: number;
  default_portion_label?: string | null;
}): Promise<Food> {
  const { data } = await api.post<Food>("/foods", payload);
  return data;
}

export async function listFavoriteFoods(): Promise<Food[]> {
  const { data } = await api.get<Food[]>("/foods/favorites");
  return data;
}

export async function addFavoriteFood(foodId: number): Promise<void> {
  await api.post(`/foods/${foodId}/favorite`);
}

export async function removeFavoriteFood(foodId: number): Promise<void> {
  await api.delete(`/foods/${foodId}/favorite`);
}
