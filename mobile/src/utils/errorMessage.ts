import axios from "axios";

/**
 * Extrai uma mensagem de erro LEGÍVEL (sempre uma string) de qualquer falha de
 * API. Use SEMPRE isto em vez de ler `err.response.data.detail` direto.
 *
 * POR QUE EXISTE (era a causa da tela branca):
 * O backend (FastAPI/Pydantic) responde erro de validação — HTTP 422 — com
 * `detail` sendo uma LISTA de objetos, não uma frase:
 *   [{ "loc": ["body","password"], "msg": "String should have at least 8...",
 *      "type": "string_too_short", "ctx": { "min_length": 8 } }]
 * As telas faziam `setErro(err.response.data.detail)` e jogavam isso dentro de
 * um <Text>. Um array de objetos dentro de <Text> derruba a árvore INTEIRA do
 * React ("Objects are not valid as a React child") — e o usuário vê só uma
 * TELA BRANCA. Era exatamente o crash de "digitei no login algo que não é
 * e-mail" (o @handle virava um 422 de e-mail inválido) e o de "criei conta com
 * senha curta". Aqui a lista vira uma frase amigável e NUNCA escapa um objeto
 * pro render.
 */
export function mensagemDeErro(err: unknown, fallback: string): string {
  const detail = (err as any)?.response?.data?.detail;

  if (typeof detail === "string" && detail.trim()) return detail;

  // 422 do FastAPI: lista de erros de validação.
  if (Array.isArray(detail)) {
    const msgs: string[] = [];
    for (const item of detail) {
      const m = traduzValidacao(item);
      if (m && !msgs.includes(m)) msgs.push(m);
    }
    if (msgs.length) return msgs.join("\n");
  }

  // Alguns erros vêm como um objeto único { msg, loc, type }.
  if (detail && typeof detail === "object") {
    const m = traduzValidacao(detail);
    if (m) return m;
  }

  // Sem `response` = a requisição nem chegou (rede fora, tempo esgotado).
  if (axios.isAxiosError(err) && !err.response) {
    return "Sem conexão com o servidor. Confira sua internet e tente de novo.";
  }

  return fallback;
}

const CAMPO_PT: Record<string, string> = {
  email: "E-mail",
  password: "Senha",
  handle: "@handle",
  display_name: "Nome de exibição",
};

/** Transforma UM item de erro de validação do Pydantic numa frase em pt-BR.
 * Sempre devolve string (ou null se o item for inválido) — nunca um objeto. */
function traduzValidacao(d: any): string | null {
  if (!d || typeof d !== "object") return null;

  const loc = Array.isArray(d.loc) ? d.loc : [];
  const campo = String(loc[loc.length - 1] ?? "");
  const label = CAMPO_PT[campo];
  const tipo = String(d.type ?? "");
  const min = d?.ctx?.min_length;
  const msgCrua = typeof d.msg === "string" ? d.msg : "";

  if (campo === "email" && (tipo.includes("value_error") || /email/i.test(msgCrua))) {
    return "Digite um e-mail válido (ex.: voce@email.com).";
  }
  if (campo === "password" && (tipo === "string_too_short" || min)) {
    return `A senha precisa ter pelo menos ${min ?? 8} caracteres.`;
  }
  if (tipo === "missing") {
    return label ? `${label}: campo obrigatório.` : "Preencha todos os campos.";
  }
  if (tipo === "string_too_short" && min) {
    return label ? `${label}: mínimo de ${min} caracteres.` : `Mínimo de ${min} caracteres.`;
  }

  // Não reconheceu: devolve a mensagem crua do backend. É uma string — seguro
  // renderizar, mesmo que em inglês. O que importa é nunca vazar um objeto.
  if (label && msgCrua) return `${label}: ${msgCrua}`;
  return msgCrua || null;
}
