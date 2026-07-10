from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class AskResponse(BaseModel):
    reply: str
    answered: bool


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Assistente determinístico (SEM IA/token): responde sobre os dados do
    usuário e conhecimento fitness. Livre — faz parte do produto manual."""
    return assistant.answer(db, current_user.id, payload.text)
