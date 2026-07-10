from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.orchestrator import run_chat_turn
from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import Plan, User
from app.services import assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Modelo mais barato da Anthropic — usado pro fallback de IA deste assistente
# único (dados/conhecimento são grátis via motor determinístico; só o que ele
# não sabe passa pela IA, então o custo real por usuário fica baixo).
_AI_MODEL = "claude-haiku-4-5-20251001"


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class AskResponse(BaseModel):
    reply: str
    answered: bool
    source: str = "app"  # "app" = determinístico grátis | "ai" = IA (Claude)
    credits_left: int | None = None  # créditos-isca restantes do Free (None = Pro/ilimitado)
    proposed_action: dict | None = None  # ação que a IA propôs (ex: criar dieta/treino) — precisa confirmação


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Assistente híbrido — ÚNICO ponto de entrada de IA do app. Tenta primeiro
    o determinístico (SEM IA, grátis): dados do usuário, conhecimento fitness
    e registro de comida. Se ele não souber (ou não conseguir identificar um
    alimento/número), cai na IA (Claude, com ferramentas — pode montar dieta e
    treino personalizados, propor registro, etc., sempre com confirmação do
    usuário antes de salvar) — ilimitada no Pro, limitada aos créditos-isca no
    Free. Sem chave/sem créditos: devolve o fallback amigável do determinístico."""
    result = assistant.answer(db, current_user.id, payload.text)
    if result.get("answered"):
        return result  # resolvido de graça, nem toca na IA

    is_pro = current_user.plan == Plan.PRO
    has_credit = is_pro or current_user.ai_free_credits > 0
    if settings.anthropic_api_key and has_credit:
        try:
            ai_result = run_chat_turn(db, current_user.id, payload.text, model=_AI_MODEL)
        except Exception:
            ai_result = None
        if ai_result and ai_result.get("reply"):
            if not is_pro:
                current_user.ai_free_credits = max(current_user.ai_free_credits - 1, 0)
                db.add(current_user)
                db.commit()
            return {
                "reply": ai_result["reply"],
                "answered": True,
                "source": "ai",
                "credits_left": None if is_pro else current_user.ai_free_credits,
                "proposed_action": ai_result.get("proposed_action"),
            }

    # Sem IA disponível (sem chave, sem créditos, ou erro): fallback determinístico.
    return result
