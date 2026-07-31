from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QuestionnaireSchema(BaseModel):
    """Estrutura das etapas — o app desenha a tela a partir disto."""

    steps: list[dict[str, Any]]
    required: list[str]


class QuestionnaireDraftUpdate(BaseModel):
    """Progresso salvo ao avançar/voltar/minimizar. `answers` é o mapa inteiro
    (não um patch): o app é dono do rascunho enquanto edita."""

    answers: dict[str, Any] = Field(default_factory=dict)
    step: int = Field(default=0, ge=0, le=20)


class PlanSummary(BaseModel):
    """Uma versão do plano, pro resumo e pro histórico."""

    id: int
    version: int
    status: str  # active | archived | failed
    reason: str
    changes: list[dict[str, Any]]
    components: dict[str, Any]
    created_at: datetime
    activated_at: datetime | None
    archived_at: datetime | None
    error: str | None


class ObjectiveState(BaseModel):
    """Estado completo da aba Objetivo — uma chamada decide qual tela mostrar."""

    has_plan: bool
    active_plan: PlanSummary | None
    # Respostas VALENDO agora (as que geraram o plano ativo).
    active_answers: dict[str, Any]
    # O que a pessoa está editando. Igual às ativas = sem pendência.
    draft_answers: dict[str, Any]
    draft_step: int
    # Diferenças entre rascunho e ativas — o aviso de alterações pendentes.
    pending_changes: list[dict[str, Any]]
    # Que partes do plano essas mudanças afetariam (atualização conservadora).
    impacted_components: list[str]
    # Campos obrigatórios ainda em branco: impedem concluir/atualizar.
    missing_required: list[str]
    history: list[PlanSummary]
