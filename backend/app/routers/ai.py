from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.ai.methods import list_methods
from app.ai.methods_ai import generate_method_plan
from app.ai.orchestrator import run_chat_turn
from app.ai.vision import analyze_meal_photo
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_pro_plan
from app.models.chat_message import ChatMessage
from app.models.user import Plan, User
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
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
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
