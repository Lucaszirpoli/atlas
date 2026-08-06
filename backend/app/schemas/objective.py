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
    # Quantas versões existem AO TODO. A lista acima é limitada (as mais
    # recentes), então `len(history)` travava no teto — quem estava na v36 via
    # "Histórico de planos · 20" pra sempre, como se tivesse parado de evoluir.
    history_total: int = 0


class GoalChangeRequest(BaseModel):
    """"Alterar meu objetivo": um campo só. O resto do questionário fica como
    está — trocar de objetivo não é motivo pra reperguntar altura e lesão."""

    goal: str = Field(min_length=1, max_length=30)


class GoalChangeResult(BaseModel):
    """Resposta do "Alterar meu objetivo".

    Devolve o estado novo da aba E o que aconteceu com a META DE CALORIAS, que é
    a parte que a pessoa precisa entender: quando o salto é grande, a meta não
    vai direto pro alvo — ela caminha em degraus. Sem esses números, a tela só
    conseguiria dizer "pronto", e a pessoa abriria a Dieta achando que o coach
    errou a conta."""

    state: ObjectiveState
    goal_label: str
    # kcal da meta ANTES da troca (None = a pessoa não tinha meta ainda).
    kcal_antes: int | None
    # kcal que passou a valer HOJE (o degrau, quando há transição).
    kcal_agora: int
    # kcal do destino final do novo objetivo.
    kcal_alvo: int
    # True = a meta vai chegar no alvo aos poucos, não hoje.
    em_transicao: bool
