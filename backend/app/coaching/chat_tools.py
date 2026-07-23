"""Ferramentas do chat do Coaching — é o que dá ao coach PODER sobre treino e
dieta (montar/trocar treino, trocar um exercício, gerar dieta personalizada).

Cada ferramenta chama código DETERMINÍSTICO já existente (o mesmo motor do resto
do app), então a IA decide QUANDO agir, mas o efeito é seguro e limitado: montar
treino arquiva o anterior (não deleta, regra 4), trocar exercício é um overlay
reversível, e gerar dieta não grava nada até a pessoa salvar/aplicar.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.diet_engine import MacroTarget, build_diet_plan
from app.coaching import workout_builder
from app.core.text import normalize_search_text
from app.models.coaching_action import CoachingAction
from app.models.exercise import Exercise, quality_order
from app.models.routine import Routine, RoutineExercise
from app.models.user import User
from app.services import goal_service
from app.services.nutrition_calc import compute_auto_goal

# Esquemas das ferramentas (formato tool-use da Anthropic).
TOOLS = [
    {
        "name": "montar_treino",
        "description": (
            "Monta (ou refaz) o TREINO COMPLETO da pessoa a partir das preferências dela "
            "(objetivo, experiência, ponto fraco, tempo por sessão, periodização) e salva "
            "como as rotinas ativas, arquivando o treino anterior. Use quando a pessoa pedir "
            "pra você montar/trocar/refazer o treino inteiro."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "trocar_exercicio",
        "description": (
            "Troca UM exercício específico do treino da pessoa por uma variação equivalente "
            "(mesmo músculo, estímulo novo). Use quando ela pedir pra trocar um exercício "
            "citando o nome dele (ex.: 'troca o agachamento', 'não curto a rosca scott')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "exercicio": {"type": "string", "description": "Nome do exercício a trocar."},
                "motivo": {"type": "string", "description": "Por que trocar (opcional)."},
            },
            "required": ["exercicio"],
        },
    },
    {
        "name": "gerar_dieta",
        "description": (
            "Gera uma dieta personalizada que bate a meta de calorias/macros da pessoa. "
            "NÃO grava nada — devolve o cardápio pra ela ver, salvar em PDF ou aplicar no "
            "diário. Use quando ela pedir uma dieta/cardápio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "refeicoes": {"type": "integer", "description": "Nº de refeições no dia (3 a 6)."},
                "restricoes": {"type": "array", "items": {"type": "string"},
                               "description": "Restrições (ex.: 'sem lactose', 'vegetariano')."},
                "observacao": {"type": "string", "description": "Preferência/observação (opcional)."},
            },
            "required": [],
        },
    },
]


def _resolve_macro_target(db: Session, user: User) -> MacroTarget | None:
    goal = goal_service.get_current_goal(db, user.id)
    if goal is not None:
        return MacroTarget(goal.kcal, goal.protein_g, goal.carbs_g, goal.fat_g)
    profile = getattr(user, "profile", None)
    weight = goal_service.get_latest_weight_kg(db, user.id)
    if profile is not None and weight is not None:
        auto = compute_auto_goal(
            biological_sex=profile.biological_sex, weight_kg=weight, height_cm=profile.height_cm,
            age=profile.age, activity_level=profile.activity_level, goal=profile.goal,
        )
        return MacroTarget(auto["kcal"], auto["protein_g"], auto["carbs_g"], auto["fat_g"])
    return None


def _find_user_exercise(db: Session, user_id: int, name: str) -> Exercise | None:
    """Acha o exercício que a pessoa citou — primeiro nas rotinas ATIVAS dela
    (é o que ela quer trocar), senão na base visível."""
    alvo = normalize_search_text(name)
    if not alvo:
        return None
    ativos = list(db.execute(
        select(Exercise)
        .join(RoutineExercise, RoutineExercise.exercise_id == Exercise.id)
        .join(Routine, Routine.id == RoutineExercise.routine_id)
        .where(Routine.user_id == user_id, Routine.is_archived.is_(False))
    ).scalars())
    for pool in (ativos, None):
        cands = pool if pool is not None else list(db.execute(
            select(Exercise).where(Exercise.is_hidden.is_(False), Exercise.is_custom.is_(False))
        ).scalars())
        exato = [e for e in cands if normalize_search_text(e.name) == alvo]
        if exato:
            return exato[0]
        contendo = [e for e in cands if alvo in normalize_search_text(e.name) or normalize_search_text(e.name) in alvo]
        if contendo:
            return sorted(contendo, key=lambda e: len(e.name))[0]
    return None


def _alternative(db: Session, orig: Exercise) -> Exercise | None:
    base = select(Exercise).where(
        Exercise.primary_muscle_group == orig.primary_muscle_group,
        Exercise.is_hidden.is_(False), Exercise.is_custom.is_(False), Exercise.id != orig.id,
    )
    mesmos = list(db.execute(base.where(Exercise.is_compound.is_(orig.is_compound)).order_by(*quality_order())).scalars())
    pool = mesmos or list(db.execute(base.order_by(*quality_order())).scalars())
    if not pool:
        return None
    return next((e for e in pool if e.equipment != orig.equipment), pool[0])


def run_tool(db: Session, user: User, name: str, tool_input: dict) -> dict:
    """Executa uma ferramenta. Devolve {for_model, action?, diet_plan?}:
    for_model = resultado conciso pro modelo continuar; action = confirmação pro
    app mostrar; diet_plan = cardápio (quando gerar dieta)."""
    if name == "montar_treino":
        try:
            r = workout_builder.build_and_save(db, user)
        except ValueError as exc:
            return {"for_model": {"erro": str(exc)}}
        return {
            "for_model": {"ok": True, "metodo": r["method_name"], "dias": r["days"],
                          "exercicios": r["total_exercises"], "ponto_fraco": r["weak_point_label"]},
            "action": {"type": "workout_built",
                       "summary": f"Montei seu treino: {r['method_name']} · {r['days']} dias · {r['total_exercises']} exercícios."},
        }

    if name == "trocar_exercicio":
        nome = (tool_input.get("exercicio") or "").strip()
        orig = _find_user_exercise(db, user.id, nome)
        if orig is None:
            return {"for_model": {"erro": f"Não encontrei '{nome}' no treino da pessoa."}}
        alt = _alternative(db, orig)
        if alt is None:
            return {"for_model": {"erro": f"Não achei uma variação boa pra trocar {orig.name}."}}
        # Idempotente: não duplica um swap ativo pro mesmo exercício.
        existing = db.execute(select(CoachingAction).where(
            CoachingAction.user_id == user.id, CoachingAction.kind == "exercise_swap",
            CoachingAction.exercise_id == orig.id, CoachingAction.reverted_at.is_(None),
        )).scalar_one_or_none()
        if existing is None:
            title = f"Trocar · {orig.name} → {alt.name}"
            detail = (f"Troque {orig.name} por {alt.name} — mesmo músculo, estímulo novo. Você pediu no chat "
                      "com o coach. Aparece no seu treino e dá pra desfazer.")
            db.add(CoachingAction(user_id=user.id, kind="exercise_swap", finding_key=f"chat_swap:{orig.id}",
                                  exercise_id=orig.id, exercise_name=orig.name, title=title, detail=detail,
                                  payload={"to_exercise_id": alt.id, "to_name": alt.name}))
            db.commit()
        return {
            "for_model": {"ok": True, "de": orig.name, "para": alt.name},
            "action": {"type": "exercise_swapped", "summary": f"Troquei {orig.name} por {alt.name} no seu treino."},
        }

    if name == "gerar_dieta":
        target = _resolve_macro_target(db, user)
        if target is None:
            return {"for_model": {"erro": "A pessoa ainda não tem meta de calorias/peso pra basear a dieta."}}
        try:
            refeicoes = int(tool_input.get("refeicoes") or 4)
        except (TypeError, ValueError):
            refeicoes = 4
        refeicoes = max(3, min(refeicoes, 6))
        restricoes = tool_input.get("restricoes") or []
        if not isinstance(restricoes, list):
            restricoes = []
        plan = build_diet_plan(db, target, [str(x) for x in restricoes], meals_per_day=refeicoes)
        d = plan.to_dict()
        return {
            "for_model": {"ok": True, "kcal": d["totals"]["kcal"], "proteina_g": d["totals"]["protein_g"],
                          "refeicoes": len(d["meals"])},
            "action": {"type": "diet_generated",
                       "summary": f"Montei uma dieta de {d['totals']['kcal']} kcal em {len(d['meals'])} refeições."},
            "diet_plan": d,
        }

    return {"for_model": {"erro": f"ferramenta desconhecida: {name}"}}
