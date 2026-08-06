from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.exercise import ExerciseRead


class RoutineExerciseCreate(BaseModel):
    exercise_id: int
    target_sets: int = Field(ge=1, le=20)
    target_reps_min: int = Field(ge=1, le=100)
    target_reps_max: int | None = Field(default=None, ge=1, le=100)
    rest_seconds: int = Field(default=90, ge=0, le=900)
    notes: str | None = None
    # Intenção de cada série de trabalho ("to_failure" | null). Aquecimento/
    # feeder não entram aqui (rampa calculada, não intenção de posição).
    # Rotina montada à mão não define nada (fica tudo null) — só o coach opina.
    set_intents: list[str | None] = Field(default_factory=list)


class RoutineExerciseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise: ExerciseRead
    sort_order: int
    target_sets: int
    target_reps_min: int
    target_reps_max: int | None
    rest_seconds: int
    notes: str | None
    set_intents: list[str | None] = []

    @field_validator("set_intents", mode="before")
    @classmethod
    def _null_vira_lista(cls, v):
        # Rotina criada ANTES de a coluna existir ficou com NULL no banco (o
        # ALTER não backfilla). Sem isto, ler essa rotina estoura na validação
        # da resposta e a lista de rotinas inteira volta 500 — o que é o mesmo
        # que perder o treino. Null = sem intenção nenhuma, que é o que a
        # rotina manual já significa.
        return v or []


class RoutineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exercises: list[RoutineExerciseCreate] = Field(min_length=1)


class RoutineUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exercises: list[RoutineExerciseCreate] = Field(min_length=1)


class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_archived: bool
    # "coach" | "manual" — quem montou. A tela de execução usa isto pra decidir
    # o que é editável durante o treino (ver o comentário no modelo Routine).
    origem: str = "manual"
    # Quantas vezes ESTA rotina já foi concluída na semana-calendário atual (a
    # semana da pessoa, começando no domingo). 0 = ainda não treinou. A aba
    # Treino troca o botão por causa disto — repetir um treino é permitido, mas
    # não é o plano, e a pessoa merece saber antes, não depois.
    feitos_na_semana: int = 0
    exercises: list[RoutineExerciseRead]
    created_at: datetime
