from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator import run_chat_turn
from app.ai.vision import analyze_meal_photo
from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_pro_plan
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.ai import (
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    MealPhotoAnalyzeRequest,
    MealPhotoAnalyzeResponse,
)

router = APIRouter(prefix="/ai", tags=["ai"])


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
    current_user: User = Depends(require_pro_plan),
    db: Session = Depends(get_db),
) -> dict:
    _require_api_key()
    try:
        return run_chat_turn(db, current_user.id, payload.message, payload.context_module)
    except Exception as exc:  # erro da API da Anthropic (chave inválida, rede etc.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"O assistente não conseguiu responder agora ({type(exc).__name__}). Tente de novo em instantes.",
        ) from exc


@router.get("/chat/history", response_model=list[ChatMessageRead])
def chat_history(
    limit: int = 50,
    current_user: User = Depends(require_pro_plan),
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
