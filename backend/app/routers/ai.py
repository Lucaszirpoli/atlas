from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.ai.diet_ai import enrich_plan
from app.ai.diet_engine import MacroTarget, build_diet_plan
from app.ai.methods import get_method, list_methods, recommend_method_for_profile
from app.ai.methods_ai import generate_method_plan
from app.ai.orchestrator import run_chat_turn
from app.ai.vision import analyze_meal_photo
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_pro_plan
from app.models.chat_message import ChatMessage
from app.models.user import Plan, User
from app.models.user_profile import UserProfile
from app.services import goal_service
from app.services.nutrition_calc import compute_auto_goal
from app.schemas.ai import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    MealPhotoAnalyzeRequest,
    MealPhotoAnalyzeResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class MethodSummary(BaseModel):
    key: str
    name: str
    author: str
    goal: str
    experience_min: str
    days_per_week: list[int]
    guide_excerpt: str


class GenerateTrainingRequest(BaseModel):
    method_key: str
    available_days: int | None = None
    phase_index: int = 0


@router.get("/training/methods", response_model=list[MethodSummary])
def training_methods() -> list[dict]:
    """Catálogo das metodologias (Hub de IA). Não usa IA — livre."""
    return [
        {
            "key": m.key,
            "name": m.name,
            "author": m.author,
            "goal": m.goal,
            "experience_min": m.experience_min.value,
            "days_per_week": list(m.days_per_week),
            "guide_excerpt": m.guide_excerpt,
        }
        for m in list_methods()
    ]


@router.post("/training/generate")
def training_generate(
    payload: GenerateTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Gera um treino fiel ao método escolhido. O plano é montado de forma
    determinística (sempre fiel, funciona sem IA); a explicação e as dicas por
    exercício são a camada Pro (IA sandbox). Isca: Pro ilimitado, Free tem
    créditos grátis — sem créditos, ainda recebe o plano, só sem as dicas."""
    is_pro = current_user.plan == Plan.PRO
    can_use_ai = is_pro or current_user.ai_free_credits > 0
    try:
        result = generate_method_plan(
            db, payload.method_key, payload.available_days, payload.phase_index, use_ai=can_use_ai
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if result.get("ai_used") and not is_pro:
        current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
        db.add(current_user)
        db.commit()
        result["free_credits_remaining"] = current_user.ai_free_credits
    result["ai_locked"] = not can_use_ai
    return result


class PersonalizedTrainingRequest(BaseModel):
    available_days: int | None = None


@router.post("/training/personalized")
def training_personalized(
    payload: PersonalizedTrainingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """"Monte um treino ideal pro seu perfil": escolhe automaticamente o método
    que melhor casa com experiência/objetivo/frequência da pessoa e gera o plano
    fiel a ele. Mesma isca de créditos do /training/generate."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).one_or_none()
    exp = profile.experience_level.value if profile else None
    goal = profile.goal.value if profile else None
    days = payload.available_days
    if days is None and profile is not None and profile.available_days:
        days = len(profile.available_days)

    method_key = recommend_method_for_profile(exp, goal, days)
    method = get_method(method_key)

    is_pro = current_user.plan == Plan.PRO
    can_use_ai = is_pro or current_user.ai_free_credits > 0
    result = generate_method_plan(db, method_key, days, 0, use_ai=can_use_ai)

    result["recommended"] = True
    result["recommended_reason"] = (
        f"Escolhemos {method.name} pelo seu perfil"
        + (f" ({goal})" if goal else "")
        + (f", {days}x/semana" if days else "")
        + "."
    )
    if result.get("ai_used") and not is_pro:
        current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
        db.add(current_user)
        db.commit()
        result["free_credits_remaining"] = current_user.ai_free_credits
    result["ai_locked"] = not can_use_ai
    return result


# --- IA de dieta (meta de macros com rails no código) ----------------------

class DietContext(BaseModel):
    target_kcal: int | None
    target_protein_g: float | None
    target_carbs_g: float | None
    target_fat_g: float | None
    has_goal_defined: bool
    profile_restrictions: list[str]


class GenerateDietRequest(BaseModel):
    restrictions: list[str] = []
    meals_per_day: int = 4
    variant: int = 0


def _resolve_target(db: Session, user_id: int) -> MacroTarget | None:
    """Meta de macros vigente: usa a meta salva; senão calcula do perfil+peso.
    None se não dá pra determinar (sem meta e sem perfil/peso)."""
    goal = goal_service.get_current_goal(db, user_id)
    if goal is not None:
        return MacroTarget(goal.kcal, goal.protein_g, goal.carbs_g, goal.fat_g)
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()
    weight = goal_service.get_latest_weight_kg(db, user_id)
    if profile is not None and weight is not None:
        auto = compute_auto_goal(
            biological_sex=profile.biological_sex,
            weight_kg=weight,
            height_cm=profile.height_cm,
            age=profile.age,
            activity_level=profile.activity_level,
            goal=profile.goal,
        )
        return MacroTarget(auto["kcal"], auto["protein_g"], auto["carbs_g"], auto["fat_g"])
    return None


@router.get("/diet/context", response_model=DietContext)
def diet_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DietContext:
    """Meta de macros da pessoa + restrições do perfil, pra tela pré-geração."""
    target = _resolve_target(db, current_user.id)
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).one_or_none()
    return DietContext(
        target_kcal=round(target.kcal) if target else None,
        target_protein_g=round(target.protein_g, 1) if target else None,
        target_carbs_g=round(target.carbs_g, 1) if target else None,
        target_fat_g=round(target.fat_g, 1) if target else None,
        has_goal_defined=goal_service.get_current_goal(db, current_user.id) is not None,
        profile_restrictions=list(profile.dietary_restrictions) if profile else [],
    )


@router.post("/diet/generate")
def diet_generate(
    payload: GenerateDietRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Monta uma dieta que BATE a meta de macros da pessoa. O plano é
    determinístico (sempre fiel, funciona sem IA); a explicação e as dicas por
    refeição são a camada Pro (IA sandbox). Isca: Pro ilimitado, Free tem
    créditos grátis — sem créditos, ainda recebe o plano, só sem as dicas."""
    target = _resolve_target(db, current_user.id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Defina sua meta de calorias/macros (ou complete o perfil com peso e "
                "objetivo) antes de gerar a dieta."
            ),
        )

    meals = max(3, min(payload.meals_per_day, 6))
    plan = build_diet_plan(db, target, payload.restrictions, meals_per_day=meals, variant=payload.variant)

    is_pro = current_user.plan == Plan.PRO
    can_use_ai = is_pro or current_user.ai_free_credits > 0
    result = enrich_plan(target, plan, use_ai=can_use_ai)

    if result.get("ai_used") and not is_pro:
        current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
        db.add(current_user)
        db.commit()
        result["free_credits_remaining"] = current_user.ai_free_credits
    result["ai_locked"] = not can_use_ai
    return result


class ApplyDietItem(BaseModel):
    food_id: int
    quantity_g: float


class ApplyDietMeal(BaseModel):
    category: str
    items: list[ApplyDietItem]


class ApplyDietRequest(BaseModel):
    meals: list[ApplyDietMeal]


@router.post("/diet/apply")
def diet_apply(
    payload: ApplyDietRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Registra a dieta gerada no diário de HOJE (append-only), uma refeição por
    categoria. A pessoa pode editar/remover depois no módulo de nutrição."""
    from datetime import datetime, timezone

    from app.schemas.meal import MealLogCreate, MealLogItemCreate
    from app.services import meal_service

    categories = {c.name: c for c in meal_service.ensure_default_categories(db, current_user.id)}
    db.flush()
    now = datetime.now(timezone.utc)
    logged_meals = logged_items = 0
    for meal in payload.meals:
        cat = categories.get(meal.category)
        if cat is None or not meal.items:
            continue
        meal_service.log_meal(
            db,
            current_user.id,
            MealLogCreate(
                meal_category_id=cat.id,
                logged_at=now,
                items=[MealLogItemCreate(food_id=i.food_id, quantity_g=i.quantity_g) for i in meal.items],
            ),
        )
        logged_meals += 1
        logged_items += len(meal.items)
    db.commit()
    return {"meals_logged": logged_meals, "items_logged": logged_items}


def _require_api_key() -> None:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "A IA ainda não foi configurada neste servidor: falta a chave "
                "ANTHROPIC_API_KEY no .env do backend. Peça ao administrador "
                "para configurá-la e reiniciar a API."
            ),
        )


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_api_key()
    # Isca: Pro é ilimitado; Free tem alguns créditos grátis para provar a IA.
    is_pro = current_user.plan == Plan.PRO
    if not is_pro:
        if current_user.ai_free_credits <= 0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    "Você usou suas mensagens grátis com o assistente. Assine o Pro "
                    "para conversar sem limite, montar treino por IA e registrar refeição por foto."
                ),
            )
    try:
        result = run_chat_turn(db, current_user.id, payload.message, payload.context_module)
    except Exception as exc:  # erro da API da Anthropic (chave inválida, rede etc.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"O assistente não conseguiu responder agora ({type(exc).__name__}). Tente de novo em instantes.",
        ) from exc

    if not is_pro:
        current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
        db.add(current_user)
        db.commit()
        result["free_credits_remaining"] = current_user.ai_free_credits
    return result


@router.get("/chat/history", response_model=list[ChatMessageRead])
def chat_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    # Ordena por ID (ordem de inserção), NÃO por created_at: user e assistant
    # de um mesmo turno eram gravados no mesmo segundo, então created_at
    # empatava e a ordem embaralhava ao reabrir a conversa. O id é monotônico,
    # então reflete a ordem cronológica real sem empate.
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars())
    rows.reverse()
    return rows


@router.post("/meal-photo", response_model=MealPhotoAnalyzeResponse)
def analyze_photo(
    payload: MealPhotoAnalyzeRequest,
    current_user: User = Depends(require_pro_plan),
    db: Session = Depends(get_db),
) -> dict:
    _require_api_key()
    try:
        return analyze_meal_photo(db, payload.image_base64, payload.media_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não consegui analisar a foto agora ({type(exc).__name__}). Tente de novo.",
        ) from exc
