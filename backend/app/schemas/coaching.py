from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoachingFinding(BaseModel):
    key: str
    severity: str  # info | attention | action
    title: str
    detail: str
    proposal: str | None = None
    # Presente só quando o ajuste é aplicável (ex.: {"kcal_delta": -200}).
    adjustment: dict[str, Any] | None = None


class ApplyDietRequest(BaseModel):
    finding_key: str


class ApplyDietResult(BaseModel):
    applied: bool
    previous_kcal: float
    new_kcal: float
    kcal_delta: int
    message: str


class CoachingAdjustmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_key: str
    kind: str
    kcal_delta: float
    prev_kcal: float
    new_kcal: float
    created_at: datetime
    reverted_at: datetime | None


class RevertResult(BaseModel):
    reverted: bool
    restored_kcal: float
    message: str


class ApplyTechniqueRequest(BaseModel):
    finding_key: str  # "stalled_lift:{exercise_id}"


class ApplyTechniqueResult(BaseModel):
    applied: bool
    exercise_name: str
    technique_label: str
    message: str


class TechniqueCueRead(BaseModel):
    """Dica ativa de técnica — a prévia do treino usa pra mostrar em cima do
    exercício correspondente."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise_name: str
    technique: str
    technique_label: str
    cue_text: str
    created_at: datetime


class RemoveCueResult(BaseModel):
    removed: bool
    message: str


class ResetBaselineResult(BaseModel):
    reset: bool
    effective_from: datetime
    message: str


class CoachChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class CoachChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[CoachChatMessage] = Field(default_factory=list)


class CoachChatResponse(BaseModel):
    answer: str
    used_ai: bool


class CoachingInsight(BaseModel):
    key: str  # peso | calorias | macros | sono | carga | treino
    severity: str
    title: str
    detail: str
    chart: str | None = None
    finding_key: str | None = None
    adjustment: dict[str, Any] | None = None


class CoachingAnalysis(BaseModel):
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str  # alta | parcial | baixa
    headline: str
    findings: list[CoachingFinding]
    insights: list[CoachingInsight] = []
    data_gaps: list[str]
    metrics: dict[str, Any]


# --- Ações de treino (progressão / troca / deload) e overlays -----------------
class ApplyActionRequest(BaseModel):
    finding_key: str  # "progression:{id}" | "deload" | "swap:{id}"


class ApplyActionResult(BaseModel):
    applied: bool
    kind: str
    title: str
    message: str


class SwapAlternative(BaseModel):
    exercise_id: int
    name: str


class CoachingActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    exercise_id: int | None
    exercise_name: str | None
    title: str
    detail: str
    payload: dict[str, Any] = {}
    created_at: datetime
    reverted_at: datetime | None


class WorkoutOverlay(BaseModel):
    """Overlay ativo do coach pra o lado do treino. `source` diz qual endpoint
    desfaz ('technique' | 'action'); `exercise_id` None = banner global (deload)."""

    source: str            # technique | action
    id: int
    kind: str              # technique | progression | exercise_swap | deload
    exercise_id: int | None
    exercise_name: str | None
    title: str
    detail: str
    payload: dict[str, Any] = {}


class CoachingChange(BaseModel):
    """Item do painel 'O que o coach mudou' — normaliza dieta, técnica e ações
    numa lista só. `source`+`ref_id` dizem qual endpoint desfaz."""

    source: str            # diet | technique | action
    ref_id: int
    icon: str              # nutrition | barbell | trending-up | swap-horizontal | bed
    title: str
    subtitle: str
    created_at: datetime
    active: bool


class RemoveActionResult(BaseModel):
    removed: bool
    message: str


class SetPaceRequest(BaseModel):
    pace: str  # slow | normal | fast


class SetTargetWeightRequest(BaseModel):
    target_weight_kg: float | None = Field(default=None, ge=25, le=400)


class SetGoalConfigResult(BaseModel):
    ok: bool
    message: str


class BuildWorkoutResult(BaseModel):
    """Resultado de montar o treino completo pelo coach (a partir das prefs)."""

    method_name: str
    author: str
    days: int
    routines: list[str]
    total_exercises: int
    weak_point_label: str | None = None
    session_range: str | None = None
    cardio_note: str | None = None
    periodization_label: str
    message: str


class SetTrainingPrefsRequest(BaseModel):
    """Preferências de treino do Coaching. Atualização PARCIAL: só os campos
    enviados (model_fields_set) são alterados — um campo omitido não é mexido,
    e enviar null limpa (ex.: tirar o ponto fraco)."""

    weak_point: str | None = None       # grupo muscular | null (nenhum)
    session_length: str | None = None   # curto | medio | longo | null
    wants_cardio: bool | None = None     # true | false | null (não escolheu)
    periodization: str | None = None     # auto | linear | ondulatoria


class CheckinLine(BaseModel):
    key: str
    status: str            # good | warn | info
    text: str


class CoachingCheckin(BaseModel):
    window_days: int
    goal: str | None
    has_data: bool
    headline: str
    wins_count: int
    lines: list[CheckinLine]
