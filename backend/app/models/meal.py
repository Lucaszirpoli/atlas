from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

DEFAULT_MEAL_CATEGORY_NAMES = [
    "Café da manhã",
    "Lanche da manhã",
    "Almoço",
    "Lanche da tarde",
    "Jantar",
    "Ceia",
]


class MealCategory(Base):
    """Categoria de refeição, por usuário e totalmente customizável (renomear,
    adicionar, remover). As 6 categorias padrão são criadas no primeiro acesso."""

    __tablename__ = "meal_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MealLog(Base):
    """Refeição registrada. Append-only — editar quantidade de um item é uma
    operação permitida (o usuário errou e corrige na hora), mas a refeição
    nunca é reescrita silenciosamente depois de um tempo; ela fica no
    histórico com a data em que foi de fato registrada."""

    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    meal_category_id: Mapped[int] = mapped_column(ForeignKey("meal_categories.id"))
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["MealLogItem"]] = relationship(
        back_populates="meal_log", cascade="all, delete-orphan"
    )


class MealLogItem(Base):
    """Um alimento dentro de uma refeição registrada. Os valores nutricionais
    são um snapshot no momento do registro (quantidade x tabela do Food
    naquele instante), para o histórico nunca mudar se o dado do alimento
    for corrigido depois."""

    __tablename__ = "meal_log_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_log_id: Mapped[int] = mapped_column(ForeignKey("meal_logs.id", ondelete="CASCADE"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    quantity_g: Mapped[float] = mapped_column(Float)

    kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    meal_log: Mapped["MealLog"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship()
