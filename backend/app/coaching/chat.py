"""Camada conversacional do Coaching (Pro) — a IA que EXPLICA, tira dúvidas e,
agora, AGE: monta/troca treino, troca exercício e gera dieta personalizada.

O motor determinístico (metrics/engine) segue sendo a VERDADE que ancora a
conversa (o modelo não inventa número nem contradiz a análise). O que mudou é
que o coach tem FERRAMENTAS (app/coaching/chat_tools) pra realmente mexer no
treino e na dieta — cada uma chama código determinístico e seguro (arquivar em
vez de deletar, overlay reversível, dieta que só grava se a pessoa aplicar).
Sem chave da Anthropic, cai num resumo determinístico (sem ações).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.coaching import chat_tools
from app.coaching.engine import WeeklyAnalysis
from app.core.config import settings
from app.models.user import User

_MODEL = settings.anthropic_model
_MAX_HISTORY = 8
_MAX_TOOL_ROUNDS = 5


def _system_prompt(analysis: WeeklyAnalysis) -> str:
    m = analysis.metrics
    linhas = [
        "Você é o coach pessoal do usuário dentro do app ATLAS (fitness/nutrição). "
        "Fala português do Brasil, tom de professor experiente: direto, acolhedor, motivador, "
        "SEM culpa ou vergonha, SEM jargão desnecessário.",
        "",
        "VOCÊ TEM AUTORIDADE sobre o treino e a dieta desta pessoa e pode AGIR pelas ferramentas:",
        "- montar_treino: monta/refaz o treino inteiro pelas preferências dela (arquiva o anterior).",
        "- trocar_exercicio: troca UM exercício citado por outro, de verdade, na rotina (edição definitiva).",
        "- registrar_refeicao: registra no diário os alimentos que ela contar que comeu — chame sempre que "
        "ela mencionar o que comeu, mesmo sem pedir explicitamente pra registrar (ex.: 'comi arroz e frango "
        "no almoço' já é um pedido implícito de registro).",
        "- gerar_dieta: monta um cardápio que bate a meta de macros (a pessoa salva/aplica depois).",
        "Use uma ferramenta SÓ quando a pessoa claramente pedir/contar aquilo. Depois de agir, confirme "
        "em 1-2 frases o que você fez. Não invente que fez algo sem chamar a ferramenta.",
        "",
        "REGRAS INEGOCIÁVEIS:",
        "- A ANÁLISE abaixo foi calculada por um motor determinístico e é a VERDADE. "
        "Baseie a conversa nela. NUNCA invente números nem a contradiga.",
        "- Se não há dado suficiente pra afirmar algo, diga isso com honestidade.",
        "- NÃO dê diagnóstico médico. Sono/saúde viram sugestão de hábito, nunca laudo.",
        "- Ajuste de CALORIAS da meta você NÃO muda na conversa — direciona pro card 'Aplicar ajuste'. "
        "(Gerar um cardápio novo é diferente e pode.)",
        "- Respostas curtas (2 a 5 frases). Nada de listas gigantes.",
        "",
        f"ANÁLISE ATUAL (janela de {analysis.window_days} dias, objetivo: {analysis.goal or 'não definido'}):",
        f"- Resumo: {analysis.headline}",
        f"- Confiança: {analysis.confidence}",
        f"- Peso: {m.get('weight_kg')} kg, tendência {m.get('weight_trend_kg_per_week')} kg/sem "
        f"({m.get('weight_pct_per_week')}%/sem), {m.get('weight_points')} registros.",
        f"- Calorias: média {m.get('avg_kcal')} kcal/dia vs meta {m.get('goal_kcal')}; "
        f"proteína média {m.get('avg_protein_g')} g vs alvo {m.get('protein_target_g')} g; "
        f"{m.get('days_logged')} dias registrados.",
        f"- Treino: {m.get('sessions_per_week')} sessões/semana. Sono: {m.get('avg_sleep_hours')} h/noite.",
    ]
    if analysis.findings:
        linhas.append("- Achados e ajustes sugeridos:")
        for f in analysis.findings:
            prop = f" Sugestão: {f.proposal}" if f.proposal else ""
            linhas.append(f"  • [{f.severity}] {f.title}: {f.detail}{prop}")
    if analysis.data_gaps:
        linhas.append("- Faltam dados: " + " ".join(analysis.data_gaps))
    return "\n".join(linhas)


def _fallback(analysis: WeeklyAnalysis, question: str) -> str:
    """Sem IA: devolve o essencial da análise, com honestidade."""
    partes = [analysis.headline]
    top = next((f for f in analysis.findings if f.severity in {"action", "attention"}), None)
    if top:
        partes.append(f"{top.title}: {top.detail}")
        if top.proposal:
            partes.append(f"Sugestão: {top.proposal}")
    partes.append(
        "Pra conversar mais a fundo sobre isso, a IA do Coaching precisa estar ativa no seu plano."
    )
    return " ".join(partes)


def _result(answer: str, used_ai: bool, actions: list[dict], diet_plan: dict | None) -> dict:
    return {"answer": answer, "used_ai": used_ai, "actions": actions, "diet_plan": diet_plan}


def answer(
    db: Session, user: User, analysis: WeeklyAnalysis, question: str, history: list[dict] | None = None
) -> dict:
    """Responde ancorado na análise e, quando a pessoa pede, AGE (monta/troca
    treino, gera dieta) via ferramentas. Retorna {answer, used_ai, actions,
    diet_plan}. Sem chave, cai no resumo determinístico (sem ações)."""
    if not settings.anthropic_api_key.strip():
        return _result(_fallback(analysis, question), False, [], None)

    msgs: list = []
    for h in (history or [])[-_MAX_HISTORY:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": question.strip()})

    actions: list[dict] = []
    diet_plan: dict | None = None
    client = get_client()
    system = _system_prompt(analysis)

    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            resp = client.messages.create(
                model=_MODEL, max_tokens=900, system=system, tools=chat_tools.TOOLS, messages=msgs,
            )
            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            if resp.stop_reason == "tool_use" and tool_uses:
                msgs.append({"role": "assistant", "content": resp.content})
                results = []
                for tu in tool_uses:
                    out = chat_tools.run_tool(db, user, tu.name, dict(tu.input or {}))
                    if out.get("action"):
                        actions.append(out["action"])
                    if out.get("diet_plan") is not None:
                        diet_plan = out["diet_plan"]
                    results.append({
                        "type": "tool_result", "tool_use_id": tu.id,
                        "content": json.dumps(out.get("for_model", {}), ensure_ascii=False),
                    })
                msgs.append({"role": "user", "content": results})
                continue
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            if not text and actions:
                text = " ".join(a["summary"] for a in actions)
            return _result(text or _fallback(analysis, question), True, actions, diet_plan)
        # Esgotou as rodadas — devolve o que já foi feito.
        resumo = " ".join(a["summary"] for a in actions) or "Feito."
        return _result(resumo, True, actions, diet_plan)
    except Exception:
        # Qualquer erro de rede/modelo: a tela nunca quebra. Mantém o que já agiu.
        return _result(_fallback(analysis, question), False, actions, diet_plan)
