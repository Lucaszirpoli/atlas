from pydantic import BaseModel, Field, model_validator

from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    ExperienceLevel,
    Goal,
    TrainingLocation,
    TrainingStylePreference,
)


class OnboardingRequest(BaseModel):
    biological_sex: BiologicalSex
    age: int = Field(ge=13, le=100)
    height_cm: float = Field(ge=100, le=250)
    current_weight_kg: float = Field(ge=30, le=300)
    activity_level: ActivityLevel
    goal: Goal
    experience_level: ExperienceLevel
    training_location: TrainingLocation
    training_style_preference: TrainingStylePreference = (
        TrainingStylePreference.IA_DECIDE
    )
    available_days: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    injuries_limitations: str | None = None
    preferred_advanced_technique: str | None = None
    trains_with_partner: bool = False
    partner_handle: str | None = None

    accepted_lgpd_health_data: bool
    accepted_medical_disclaimer: bool

    @model_validator(mode="after")
    def consents_must_be_accepted(self) -> "OnboardingRequest":
        if not self.accepted_lgpd_health_data or not self.accepted_medical_disclaimer:
            raise ValueError(
                "É necessário aceitar o consentimento LGPD e o disclaimer médico "
                "para concluir o onboarding"
            )
        return self


class OnboardingResponse(BaseModel):
    onboarding_completed: bool
