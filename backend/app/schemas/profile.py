from pydantic import BaseModel, ConfigDict, Field

from app.models.user_profile import ActivityLevel, BiologicalSex, Goal


class ProfileCalcRead(BaseModel):
    """Campos do perfil que entram no cálculo automático de metas, mais o
    peso mais recente (que vem dos registros de peso, não do perfil)."""

    model_config = ConfigDict(from_attributes=True)

    biological_sex: BiologicalSex
    age: int
    height_cm: float
    activity_level: ActivityLevel
    goal: Goal
    current_weight_kg: float | None = None


class ProfileCalcUpdate(BaseModel):
    """Atualização parcial dos campos do cálculo automático. Todos opcionais —
    só o que vier é alterado. current_weight_kg, se enviado, vira um novo
    registro de peso (append-only, não sobrescreve o histórico)."""

    biological_sex: BiologicalSex | None = None
    age: int | None = Field(default=None, ge=13, le=100)
    height_cm: float | None = Field(default=None, ge=100, le=250)
    activity_level: ActivityLevel | None = None
    goal: Goal | None = None
    current_weight_kg: float | None = Field(default=None, ge=30, le=300)
