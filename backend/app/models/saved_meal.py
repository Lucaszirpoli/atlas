from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class SavedMeal(Base):
    """Refeição salva pelo usuário para reuso rápido (ex: 'meu café da manhã')."""

    __tablename__ = "saved_meals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[list["SavedMealItem"]] = relationship(
        back_populates="saved_meal", cascade="all, delete-orphan"
    )


class SavedMealItem(Base):
    __tablename__ = "saved_meal_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    saved_meal_id: Mapped[int] = mapped_column(ForeignKey("saved_meals.id", ondelete="CASCADE"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    quantity_g: Mapped[float] = mapped_column(Float)

    saved_meal: Mapped["SavedMeal"] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship()


class FavoriteFood(Base):
    __tablename__ = "favorite_foods"
    __table_args__ = (UniqueConstraint("user_id", "food_id", name="uq_favorite_user_food"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
