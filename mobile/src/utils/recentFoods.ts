import AsyncStorage from "@react-native-async-storage/async-storage";

import type { Food } from "../api/foods";

/**
 * Últimos alimentos usados, no aparelho.
 *
 * Fica local de propósito: é atalho de digitação, não dado de saúde. Não
 * precisa de tabela, de sincronizar entre aparelhos, nem de consentimento LGPD
 * — e o histórico REAL do que a pessoa comeu já está no diário, no servidor.
 */

const CHAVE = "@appfit/recent_foods";
const MAX = 12;

export async function listRecentFoods(): Promise<Food[]> {
  try {
    const cru = await AsyncStorage.getItem(CHAVE);
    if (!cru) return [];
    const lista = JSON.parse(cru);
    return Array.isArray(lista) ? lista : [];
  } catch {
    // Storage corrompido não pode derrubar a busca de alimento.
    return [];
  }
}

export async function addRecentFood(food: Food): Promise<void> {
  try {
    const atuais = await listRecentFoods();
    // O mais recente primeiro, sem repetir. Reusar um alimento antigo o traz
    // de volta pro topo — que é o comportamento esperado de "recentes".
    const novos = [food, ...atuais.filter((f) => f.id !== food.id)].slice(0, MAX);
    await AsyncStorage.setItem(CHAVE, JSON.stringify(novos));
  } catch {
    // Falhar em gravar atalho nunca pode atrapalhar o registro da refeição.
  }
}
