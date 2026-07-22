from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_transition import CoachingTransition
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.services.nutrition_calc import compute_auto_goal

SIGNIFICANT_KCAL_DELTA = 100
# Passo máximo de mudança de meta por vez, quando a troca é grande. Acima disso o
# coach faz TRANSIÇÃO gradual (não estoura as calorias de um dia pro outro).
TRANSITION_STEP_KCAL = 250
# Dias mínimos entre um passo da transição e o próximo (ritmo semanal, saudável).
TRANSITION_MIN_DAYS = 4


def get_current_goal(db: Session, user_id: int) -> CalorieGoal | None:
    return db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_latest_weight_kg(db: Session, user_id: int) -> float | None:
    log = db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == user_id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return log.weight_kg if log else None


def compute_suggestion(db: Session, user_id: int, profile: UserProfile) -> dict:
    weight_kg = get_latest_weight_kg(db, user_id)
    if weight_kg is None:
        raise ValueError("Usuário ainda não tem peso registrado")

    suggestion = compute_auto_goal(
        biological_sex=profile.biological_sex,
        weight_kg=weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        activity_level=profile.activity_level,
        goal=profile.goal,
    )

    current = get_current_goal(db, user_id)
    changed_significantly = (
        current is None or abs(current.kcal - suggestion["kcal"]) >= SIGNIFICANT_KCAL_DELTA
    )

    return {
        **suggestion,
        "current_goal": current,
        "changed_significantly": changed_significantly,
        "objective": profile.goal.value,
    }


def active_transition(db: Session, user_id: int) -> CoachingTransition | None:
    return db.execute(
        select(CoachingTransition)
        .where(CoachingTransition.user_id == user_id, CoachingTransition.completed_at.is_(None))
        .order_by(CoachingTransition.created_at.desc(), CoachingTransition.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _macros_at(kcal: float, protein_g: float, sug: dict) -> tuple[float, float]:
    """Macros de um passo intermediário: mantém a proteína do alvo (segura o
    músculo) e divide o resto na MESMA proporção carbo:gordura do objetivo, então
    o macro converge pro alvo conforme a kcal converge."""
    tc, tf = sug["carbs_g"], sug["fat_g"]
    carb_energy = tc * 4
    ratio = carb_energy / (carb_energy + tf * 9) if (carb_energy + tf * 9) > 0 else 0.5
    resto = max(0.0, kcal - protein_g * 4)
    return round(resto * ratio / 4, 1), round(resto * (1 - ratio) / 9, 1)


def apply_auto_goal(db: Session, user_id: int, suggestion: dict) -> CalorieGoal:
    """Aplica a meta automática. Se a mudança for GRANDE (troca de objetivo, salto
    de calorias), NÃO estoura de uma vez: aplica um passo capado e abre uma
    TRANSIÇÃO — o coach leva até o alvo aos poucos. Mudança pequena vai direto."""
    now = datetime.now(timezone.utc)
    current = suggestion.get("current_goal")
    target_kcal = float(suggestion["kcal"])

    prior = active_transition(db, user_id)

    if current is not None and abs(target_kcal - current.kcal) > TRANSITION_STEP_KCAL:
        passo = TRANSITION_STEP_KCAL if target_kcal > current.kcal else -TRANSITION_STEP_KCAL
        new_kcal = round(current.kcal + passo)
        carbs, fat = _macros_at(new_kcal, suggestion["protein_g"], suggestion)
        goal = CalorieGoal(user_id=user_id, mode=GoalMode.AUTO, kcal=new_kcal,
                           protein_g=suggestion["protein_g"], carbs_g=carbs, fat_g=fat)
        db.add(goal)
        if prior is not None:
            prior.completed_at = now  # troca de rumo cancela a transição antiga
        db.add(CoachingTransition(user_id=user_id, to_objective=suggestion.get("objective", ""),
                                  from_kcal=current.kcal, target_kcal=target_kcal))
        db.commit()
        db.refresh(goal)
        return goal

    # Mudança pequena (ou primeira meta): aplica cheia e encerra transição aberta.
    goal = CalorieGoal(user_id=user_id, mode=GoalMode.AUTO, kcal=suggestion["kcal"],
                       protein_g=suggestion["protein_g"], carbs_g=suggestion["carbs_g"],
                       fat_g=suggestion["fat_g"])
    db.add(goal)
    if prior is not None:
        prior.completed_at = now
    db.commit()
    db.refresh(goal)
    return goal


def days_since_last_goal(db: Session, user_id: int) -> int | None:
    g = get_current_goal(db, user_id)
    if g is None or g.created_at is None:
        return None
    created = g.created_at if g.created_at.tzinfo else g.created_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).days


def step_transition_goal(db: Session, user_id: int, profile: UserProfile) -> dict:
    """Dá o PRÓXIMO passo de uma transição: recalcula o alvo (acompanha o peso) e
    move a meta um passo em direção a ele. Chegou perto → aplica o alvo cheio e
    conclui a transição. Respeita o intervalo mínimo entre passos (ritmo saudável).
    Levanta ValueError (o router vira 409) quando não cabe dar um passo agora."""
    tr = active_transition(db, user_id)
    if tr is None:
        raise ValueError("Você não está em transição de objetivo.")
    current = get_current_goal(db, user_id)
    if current is None:
        raise ValueError("Defina sua meta antes.")
    dias = days_since_last_goal(db, user_id)
    if dias is not None and dias < TRANSITION_MIN_DAYS:
        raise ValueError(f"O próximo passo da transição é daqui a {TRANSITION_MIN_DAYS - dias} dia(s) — "
                         "subir/descer calorias devagar é o que protege o resultado.")

    sug = compute_suggestion(db, user_id, profile)
    target_kcal = float(sug["kcal"])
    now = datetime.now(timezone.utc)

    if abs(target_kcal - current.kcal) <= TRANSITION_STEP_KCAL:
        # último passo — chega no alvo e conclui.
        new_kcal = round(target_kcal)
        carbs, fat = sug["carbs_g"], sug["fat_g"]
        tr.completed_at = now
        completed = True
    else:
        passo = TRANSITION_STEP_KCAL if target_kcal > current.kcal else -TRANSITION_STEP_KCAL
        new_kcal = round(current.kcal + passo)
        carbs, fat = _macros_at(new_kcal, sug["protein_g"], sug)
        completed = False

    goal = CalorieGoal(user_id=user_id, mode=GoalMode.AUTO, kcal=new_kcal,
                       protein_g=sug["protein_g"], carbs_g=carbs, fat_g=fat)
    db.add(goal)
    # NÃO commita aqui — o router loga o CoachingAdjustment na MESMA transação.
    db.flush()
    return {"prev_goal": current, "new_goal": goal, "target_kcal": target_kcal,
            "completed": completed, "new_kcal": new_kcal}


def apply_manual_goal(db: Session, user_id: int, payload) -> CalorieGoal:
    goal = CalorieGoal(
        user_id=user_id,
        mode=GoalMode.MANUAL,
        kcal=payload.kcal,
        protein_g=payload.protein_g,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        fiber_g=payload.fiber_g,
        sodium_mg=payload.sodium_mg,
        sugar_g=payload.sugar_g,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal
