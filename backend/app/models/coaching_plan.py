import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlanStatus(str, enum.Enum):
    """Um plano só existe em três estados. `ACTIVE` é único por usuário."""

    # Gerado com sucesso e valendo agora.
    ACTIVE = "active"
    # Foi ativo, virou histórico quando um novo entrou no lugar.
    ARCHIVED = "archived"
    # A geração começou e falhou no meio. Fica registrado (auditoria) e NUNCA
    # substitui nada — a regra de segurança da spec §12 é que uma atualização
    # que falha não ativa componente nenhum e não toca nas respostas ativas.
    FAILED = "failed"


class CoachingPlan(Base):
    """Uma VERSÃO do plano do Coaching (spec §3, §4 e §12).

    Um plano amarra, numa coisa só e com número de versão: as respostas do
    questionário que o originaram, o treino gerado, as metas nutricionais, a
    dieta em PDF, a periodização e a análise. Existe por dois motivos:

    1. **Ativação atômica.** Antes, cada peça era gerada e aplicada por conta
       própria — dava pra ficar com treino novo e meta antiga ao mesmo tempo,
       cada aba mostrando uma versão diferente da verdade. Agora o plano só vira
       ACTIVE quando TODOS os componentes ficaram prontos; se algo falhar, ele
       nasce FAILED e o plano anterior continua intacto.
    2. **Histórico e rastreabilidade.** Dá pra dizer o que mudou, quando, por
       quê e com base em quais respostas — e comparar com o plano anterior.

    Append-only: atualizar cria uma linha nova e arquiva a anterior. Nada é
    sobrescrito nem apagado (regra 4).
    """

    __tablename__ = "coaching_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # 1, 2, 3... por usuário. É o "v3" que a pessoa vê no histórico.
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status", native_enum=False), default=PlanStatus.ACTIVE, index=True
    )

    # Respostas do questionário que geraram ESTA versão. Snapshot: mudar o
    # perfil depois não reescreve o que foi usado aqui (rastreabilidade).
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    # O que mudou em relação à versão anterior — a comunicação clara ao usuário
    # ("dias de treino: 3 -> 4", "calorias: 2400 -> 2250").
    changes: Mapped[list] = mapped_column(JSON, default=list)
    # Referências dos componentes gerados (routine_ids, calorie_goal_id...).
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    # Por que esta versão nasceu: "primeiro_plano" | "atualizacao" | ...
    reason: Mapped[str] = mapped_column(String(30), default="atualizacao")
    # Preenchido quando status=FAILED: o que impediu a ativação.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionnaireDraft(Base):
    """Respostas em RASCUNHO do questionário da aba Objetivo.

    Cobre os dois casos da spec §3.1 e §3.5, que são o mesmo mecanismo:

    - primeiro acesso: a pessoa responde em 6 etapas e pode sair no meio; o
      progresso fica salvo e ela volta de onde parou;
    - edição depois: as respostas alteradas ficam PENDENTES e **não substituem
      as ativas** até ela confirmar e o novo plano ser gerado com sucesso.

    Uma linha por usuário — o rascunho é sempre "o que está sendo mexido agora".
    """

    __tablename__ = "questionnaire_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    # Em que etapa a pessoa parou (0..N-1), pra reabrir no lugar certo.
    step: Mapped[int] = mapped_column(Integer, default=0)
    # True depois que ela concluiu o questionário uma vez — daí em diante o
    # rascunho representa uma EDIÇÃO pendente, não um preenchimento inicial.
    completed: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
