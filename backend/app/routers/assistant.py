from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import Plan, User
from app.services import assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class AskResponse(BaseModel):
    reply: str
    answered: bool
    source: str = "app"  # "app" = determinístico grátis | "ai" = IA (Claude)
    credits_left: int | None = None  # créditos-isca restantes do Free (None = Pro/ilimitado)


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Assistente híbrido. Tenta primeiro o determinístico (SEM IA, grátis):
    dados do usuário, conhecimento fitness e registro de comida. Se ele não
    souber, e houver IA configurada, cai na IA (Claude) — ilimitada no Pro,
    limitada aos créditos-isca no Free. Sem chave/sem créditos: devolve o
    fallback amigável do determinístico."""
    result = assistant.answer(db, current_user.id, payload.text)
    if result.get("answered"):
        return result  # resolvido de graça, nem toca na IA

    is_pro = current_user.plan == Plan.PRO
    has_credit = is_pro or current_user.ai_free_credits > 0
    if settings.anthropic_api_key and has_credit:
        ai_reply = assistant.ai_fallback(db, current_user.id, payload.text)
        if ai_reply:
            if not is_pro:
                current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
                db.add(current_user)
                db.commit()
            return {
                "reply": ai_reply,
                "answered": True,
                "source": "ai",
                "credits_left": None if is_pro else current_user.ai_free_credits,
            }

    # Sem IA disponível (sem chave, sem créditos, ou erro): fallback determinístico.
    return result
