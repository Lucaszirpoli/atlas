from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.food import FoodRead


class MealCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class MealCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class MealCategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class MealLogItemCreate(BaseModel):
    food_id: int
    quantity_g: float = Field(gt=0)
    # Opcional: quando a pessoa escolheu por medida caseira ("2 unidades"),
    # o app manda o rótulo + a contagem pra guardar como foi registrado. A
    # quantidade em gramas continua obrigatória e é a base do cálculo.
    unit_label: str | None = Field(default=None, max_length=50)
    unit_amount: float | None = Field(default=None, gt=0)


class MealLogCreate(BaseModel):
    meal_category_id: int
    logged_at: datetime
    items: list[MealLogItemCreate] = Field(min_length=1)


class MealLogItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    food_id: int
    food: FoodRead
    quantity_g: float
    unit_label: str | None = None
    unit_amount: float | None = None
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    sodium_mg: float | None
    sugar_g: float | None


class MealLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meal_category_id: int
    logged_at: datetime
    items: list[MealLogItemRead]


class MealParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ParsedMealItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    raw: str
    food: FoodRead | None
    alternatives: list[FoodRead]
    quantity_g: float | None
    status: str  # ok | porcao_estimada | sem_alimento | nao_encontrado


class SavedMealItemCreate(BaseModel):
    food_id: int
    quantity_g: float = Field(gt=0)
    unit_label: str | None = Field(default=None, max_length=50)
    unit_amount: float | None = Field(default=None, gt=0)


class SavedMealCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    items: list[SavedMealItemCreate] = Field(min_length=1)


class SavedMealItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    food_id: int
    food: FoodRead
    quantity_g: float
    unit_label: str | None = None
    unit_amount: float | None = None


class SavedMealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    items: list[SavedMealItemRead]
