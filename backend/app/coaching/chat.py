"""Camada conversacional do Coaching (Pro) — a IA que EXPLICA e tira dúvidas.

Princípio da reformulação: o motor determinístico (metrics/engine) decide; a IA
só traduz isso em conversa. Por isso a análise entra no prompt como VERDADE que
o modelo tem que respeitar — ele não recalcula nada, não inventa número e não
muda plano (pra isso existe o botão "Aplicar ajuste"). Sem chave da Anthropic,
cai num resumo determinístico da própria análise.
"""

from __future__ import annotations

from app.ai.client import get_client
from app.coaching.engine import WeeklyAnalysis
from app.core.config import settings

_MODEL = settings.anthropic_model
_MAX_HISTORY = 8


def _system_prompt(analysis: WeeklyAnalysis) -> str:
    m = analysis.metrics
    linhas = [
        "Você é o coach pessoal do usuário dentro do app ATLAS (fitness/nutrição). "
        "Fala português do Brasil, tom de professor experiente: direto, acolhedor, motivador, "
        "SEM culpa ou vergonha, SEM jargão desnecessário.",
        "",
        "REGRAS INEGOCIÁVEIS:",
        "- A ANÁLISE abaixo foi calculada por um motor determinístico e é a VERDADE. "
        "Baseie TODA resposta nela. NUNCA invente números nem contradiga a análise.",
        "- Se não há dado suficiente pra afirmar algo, diga isso com honestidade.",
        "- NÃO dê diagnóstico médico. Sono/saúde viram sugestão de hábito, nunca laudo.",
        "- Você NÃO altera o plano na conversa. Se a pessoa quer aplicar um ajuste, diga pra "
        "tocar no botão 'Aplicar ajuste' do card correspondente.",
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


def answer(analysis: WeeklyAnalysis, question: str, history: list[dict] | None = None) -> tuple[str, bool]:
    """Responde a pergunta ancorada na análise. Retorna (texto, usou_ia)."""
    if not settings.anthropic_api_key.strip():
        return _fallback(analysis, question), False

    msgs: list[dict] = []
    for h in (history or [])[-_MAX_HISTORY:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": question.strip()})

    try:
        resp = get_client().messages.create(
            model=_MODEL,
            max_tokens=500,
            system=_system_prompt(analysis),
            messages=msgs,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        if not text:
            return _fallback(analysis, question), False
        return text, True
    except Exception:
        # Qualquer erro de rede/modelo cai no determinístico — a tela nunca quebra.
        return _fallback(analysis, question), False
