from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeightLogCreate(BaseModel):
    # Faixa humana plausível — evita registros absurdos (ex: 5kg) que
    # distorceriam o gráfico de evolução. Alinhado ao onboarding.
    weight_kg: float = Field(ge=25, le=400)
    recorded_at: datetime | None = None


class WeightLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    weight_kg: float
    recorded_at: datetime
