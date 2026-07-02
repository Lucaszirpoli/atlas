from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.food import FoodSource


class FoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: FoodSource
    barcode: str | None
    name: str
    brand: str | None
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float
    fiber_g_per_100g: float | None
    sodium_mg_per_100g: float | None
    sugar_g_per_100g: float | None
    default_portion_g: float
    default_portion_label: str | None


class FoodCreate(BaseModel):
    name: str
    brand: str | None = None
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float
    fiber_g_per_100g: float | None = None
    sodium_mg_per_100g: float | None = None
    sugar_g_per_100g: float | None = None
    default_portion_g: float = 100.0
    default_portion_label: str | None = None
