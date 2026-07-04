from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat_message import ChatRole


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context_module: str | None = None


class ChatResponse(BaseModel):
    reply: str
    proposed_action: dict | None = None
    free_credits_remaining: int | None = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: ChatRole
    content: str
    proposed_action: dict | None
    created_at: datetime


class MealPhotoAnalyzeRequest(BaseModel):
    image_base64: str
    media_type: str = Field(default="image/jpeg")


class MealPhotoItem(BaseModel):
    nome_identificado: str
    food_id: int | None
    quantidade_estimada_g: float
    confianca: str


class MealPhotoAnalyzeResponse(BaseModel):
    itens: list[MealPhotoItem]
    aviso: str
