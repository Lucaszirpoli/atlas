/** Normalização de texto para busca — espelha o normalize_search_text do
 * backend (app/core/text.py), pra que filtrar uma lista local no app dê o
 * mesmo resultado que buscar no servidor: "pao" acha "Pão", "cafe" acha "Café".
 */

// Faixa dos sinais diacríticos combinantes que o normalize("NFD") separa das
// letras. Escrita como escape ASCII de proposito: o caractere literal e
// invisível no editor e alguns ambientes o corrompem ao salvar.
const MARCAS_DE_ACENTO = new RegExp("[\u0300-\u036f]", "g");

/** "Pão Integral" -> "pao integral". */
export function semAcento(texto: string): string {
  return texto.toLowerCase().normalize("NFD").replace(MARCAS_DE_ACENTO, "");
}

/** Casa um termo digitado com um texto, ignorando acento e maiúscula. */
export function contemTermo(texto: string, termo: string): boolean {
  return semAcento(texto).includes(semAcento(termo));
}
