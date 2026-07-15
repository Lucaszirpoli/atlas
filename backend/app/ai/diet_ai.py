"""Camada de IA SANDBOX da geração de dieta por meta de macros.

O plano é montado pelo motor determinístico (diet_engine) — fiel à meta e
sempre válido, funciona até sem a IA. Aqui a IA entra só para ENRIQUECER: uma
explicação curta de como o cardápio bate a meta e uma dica prática por refeição
(preparo, substituição simples, ordem de comer). Ela é "cega" para o mundo
externo — o prompt a restringe ao plano que o motor já montou e à meta; ela NÃO
pode trocar alimentos nem gramas nem inventar números. Sem chave da API ou em
qualquer falha, devolve o plano determinístico puro (degradação graciosa).

Tom sensível a saúde mental (espec. 3.7): nunca linguagem de culpa/proibição;
comida é combustível, não pecado.
"""

from __future__ import annotations

import json

from app.ai.client import get_client
from app.ai.diet_engine import DietPlan, MacroTarget

_MODEL = "claude-sonnet-5"


def _sandbox_prompt(target: MacroTarget, plan: DietPlan) -> str:
    restr = ", ".join(plan.restrictions) if plan.restrictions else "nenhuma"
    return (
        "Você é um assistente de nutrição operando em MODO FECHADO. Sua única fonte é o PLANO DE "
        "REFEIÇÕES abaixo, que o sistema já montou para bater a meta de macros da pessoa. É PROIBIDO "
        "usar conhecimento externo, buscar na internet, ou inventar alimentos, gramas, calorias ou "
        "macros. Você NÃO pode alterar o plano (alimentos, porções) — ele já foi calculado. Sua tarefa "
        "é apenas: (1) escrever uma explicação curta e acolhedora de como esse cardápio atinge a meta; "
        "(2) dar uma dica prática por refeição (preparo, tempero, substituição simples equivalente, ou "
        "ordem de comer). Nunca use linguagem de culpa, proibição ou 'certo/errado' com comida — o tom "
        "é de apoio, comida é combustível. Não dê diagnóstico médico.\n\n"
        f"META DO DIA: {round(target.kcal)} kcal, {round(target.protein_g)}g proteína, "
        f"{round(target.carbs_g)}g carboidrato, {round(target.fat_g)}g gordura.\n"
        f"RESTRIÇÕES: {restr}.\n"
        "Responda SEMPRE em JSON no formato: "
        '{"intro": "<2-3 frases>", "dicas": {"<nome da refeição>": "<dica curta>"}}'
    )


def _plan_summary(plan: DietPlan) -> str:
    linhas = []
    for meal in plan.meals:
        itens = ", ".join(f"{it['food_name']} {it['quantity_g']:.0f}g" for it in meal["items"])
        linhas.append(f"- {meal['category']}: {itens}")
    return "\n".join(linhas)


def _enrich_with_ai(target: MacroTarget, plan: DietPlan) -> tuple[str | None, dict[str, str]]:
    user_msg = (
        "Plano do dia (não altere nada):\n"
        f"{_plan_summary(plan)}\n\n"
        "Escreva a explicação e uma dica curta para cada refeição listada."
    )
    client = get_client()
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=1200,
        system=_sandbox_prompt(target, plan),
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None, {}
    data = json.loads(text[start : end + 1])
    return data.get("intro"), data.get("dicas", {}) or {}


def enrich_plan(target: MacroTarget, plan: DietPlan, use_ai: bool) -> dict:
    """Devolve o plano (dict) + intro + dicas por refeição + fidelidade.
    `use_ai=False` (ou falha/sem chave) → plano determinístico puro."""
    from app.ai.diet_engine import validate_diet_plan
    from app.core.config import settings

    problems = validate_diet_plan(target, plan)
    plan_dict = plan.to_dict()

    intro: str | None = None
    dicas: dict[str, str] = {}
    ai_used = False
    if use_ai and settings.anthropic_api_key:
        try:
            intro, dicas = _enrich_with_ai(target, plan)
            ai_used = True
        except Exception:
            intro, dicas = None, {}
            ai_used = False

    if dicas:
        for meal in plan_dict["meals"]:
            if meal["category"] in dicas:
                meal["note"] = dicas[meal["category"]]

    return {
        "plan": plan_dict,
        "intro": intro,
        "ai_used": ai_used,
        "is_faithful": not problems,
        "violations": problems,
    }
