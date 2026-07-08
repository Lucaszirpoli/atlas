"""Camada de IA SANDBOX da geração de treino por metodologia.

O plano em si é montado pelo motor determinístico (methods_engine) — fiel e
sempre válido, funciona até sem a IA. Aqui a IA entra só para ENRIQUECER:
uma explicação curta de como o plano segue o método e uma dica por exercício.
Ela é "cega" para o mundo externo — o prompt a restringe EXCLUSIVAMENTE às
regras e ao trecho-fonte do método escolhido + à lista de exercícios que o
motor já selecionou. Ela não pode trocar séries/reps/ordem/exercícios nem
inventar parâmetros. Se a chave da API faltar ou a chamada falhar, devolvemos
o plano determinístico puro (degradação graciosa).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.ai.methods import MethodSpec, get_method
from app.ai.methods_engine import WorkoutPlan, build_plan, validate_plan
from app.core.config import settings

_MODEL = "claude-sonnet-5"


def _sandbox_prompt(method: MethodSpec) -> str:
    forbidden = "\n".join(f"- {f}" for f in method.forbidden) or "- (nenhuma proibição específica)"
    return (
        "Você é um assistente de treino da Arvo operando em MODO FECHADO. Suas únicas fontes são as "
        "REGRAS DO MÉTODO e o TRECHO OFICIAL abaixo. É PROIBIDO usar qualquer conhecimento externo, "
        "buscar na internet, citar outros métodos, ou inventar exercícios, séries, repetições, cadências "
        "ou percentuais. Você NÃO pode alterar a estrutura do plano (exercícios, séries, reps, ordem) — "
        "ela já foi montada pelo sistema seguindo o método. Sua tarefa é apenas: (1) escrever uma "
        "explicação curta de como este plano segue o método; (2) dar uma dica prática de execução por "
        "exercício, coerente com o método. Se algo não estiver nas fontes, diga que o guia não especifica.\n\n"
        f"MÉTODO: {method.name} — {method.author}\n"
        f"OBJETIVO: {method.goal}\n"
        f"REGRA DE PROGRESSÃO: {method.progression_rule}\n"
        f"PROIBIÇÕES DE SEGURANÇA:\n{forbidden}\n\n"
        f"TRECHO OFICIAL DO GUIA (fonte única):\n{method.guide_excerpt}\n\n"
        "Nunca contradiga o trecho oficial. Tom motivador, direto, sem culpa. Responda SEMPRE em JSON "
        'no formato: {"intro": "<2-3 frases>", "dicas": {"<nome do exercício>": "<dica curta>"}}'
    )


def _enrich_with_ai(method: MethodSpec, plan: WorkoutPlan) -> tuple[str | None, dict[str, str]]:
    exercises = sorted({sl.exercise_name for s in plan.sessions for sl in s.slots})
    user_msg = (
        f"Plano gerado ({plan.days_per_week} dias, fase: {plan.phase_context or 'base'}). "
        f"Exercícios usados: {', '.join(exercises)}.\n"
        "Escreva a explicação e uma dica curta para cada exercício listado."
    )
    client = get_client()
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=1500,
        system=_sandbox_prompt(method),
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None, {}
    data = json.loads(text[start : end + 1])
    return data.get("intro"), data.get("dicas", {}) or {}


def generate_method_plan(
    db: Session,
    method_key: str,
    available_days: int | None,
    phase_index: int = 0,
    use_ai: bool = True,
) -> dict:
    """Gera o plano fiel do método. `use_ai=True` tenta enriquecer com a IA
    sandbox; qualquer falha cai no plano determinístico puro."""
    method = get_method(method_key)
    if method is None:
        raise ValueError(f"Método desconhecido: {method_key}")

    plan = build_plan(db, method, available_days=available_days, phase_index=phase_index)
    problems = validate_plan(method, plan)

    intro: str | None = None
    dicas: dict[str, str] = {}
    ai_used = False
    if use_ai and settings.anthropic_api_key:
        try:
            intro, dicas = _enrich_with_ai(method, plan)
            ai_used = True
        except Exception:
            intro, dicas = None, {}
            ai_used = False

    plan_dict = plan.to_dict()
    if dicas:
        for session in plan_dict["sessions"]:
            for slot in session["slots"]:
                if slot["exercise_name"] in dicas:
                    slot["note"] = dicas[slot["exercise_name"]]

    return {
        "plan": plan_dict,
        "intro": intro,
        "ai_used": ai_used,
        "is_faithful": not problems,
        "violations": problems,
    }
