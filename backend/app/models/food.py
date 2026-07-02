import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FoodSource(str, enum.Enum):
    TACO = "taco"
    OPEN_FOOD_FACTS = "open_food_facts"
    CUSTOM = "custom"


class Food(Base):
    """Alimento genérico (TACO) ou produto de marca (Open Food Facts, cacheado
    localmente na primeira busca) ou cadastro customizado de um usuário."""

    __tablename__ = "foods"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_food_source_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[FoodSource] = mapped_column(Enum(FoodSource, name="food_source"))
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(200), index=True)
    brand: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Valores nutricionais por 100g/100ml, base do cálculo de qualquer porção.
    kcal_per_100g: Mapped[float] = mapped_column(Float)
    protein_g_per_100g: Mapped[float] = mapped_column(Float)
    carbs_g_per_100g: Mapped[float] = mapped_column(Float)
    fat_g_per_100g: Mapped[float] = mapped_column(Float)
    fiber_g_per_100g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg_per_100g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar_g_per_100g: Mapped[float | None] = mapped_column(Float, nullable=True)

    default_portion_g: Mapped[float] = mapped_column(Float, default=100.0)
    default_portion_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
