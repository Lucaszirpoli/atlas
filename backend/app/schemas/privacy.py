from pydantic import BaseModel, ConfigDict

from app.models.privacy_settings import ProfileVisibility


class PrivacySettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_visibility: ProfileVisibility
    share_workouts: bool
    share_meals: bool
    share_progress_photos: bool


class PrivacySettingsUpdate(BaseModel):
    profile_visibility: ProfileVisibility | None = None
    share_workouts: bool | None = None
    share_meals: bool | None = None
    share_progress_photos: bool | None = None
