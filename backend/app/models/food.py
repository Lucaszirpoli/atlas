import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.text import normalize_search_text


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

    # Nome + marca sem acento/maiúsculas — alvo da busca pra "pao" achar "Pão".
    # Preenchido automaticamente pelos listeners abaixo; nunca setar à mão.
    search_text: Mapped[str] = mapped_column(String(400), default="", index=True)

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


@event.listens_for(Food, "before_insert")
@event.listens_for(Food, "before_update")
def _populate_search_text(_mapper, _connection, target: Food) -> None:
    """Mantém search_text sempre em sincronia com name/brand — um lugar só,
    impossível esquecer em algum ponto de inserção (seed, OFF, custom)."""
    target.search_text = normalize_search_text(target.name, target.brand)


class FoodPortion(Base):
    """Medida caseira nomeada de um alimento — "unidade", "fatia", "colher de
    sopa", "concha" — com o peso em gramas de UMA unidade. Um alimento pode ter
    várias. As gramas continuam sendo a base de todo cálculo nutricional; a
    porção é só a forma humana de escolher a quantidade (ninguém pesa um ovo,
    pensa "2 unidades").

    `created_by_user_id` nulo = medida embutida (derivada da base/seed, visível
    pra todo mundo); preenchido = medida personalizada que aquele usuário criou
    pra aquele alimento (só ele vê). É o "unidades personalizadas" da Parte 3.2.
    """

    __tablename__ = "food_portions"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    # Rótulo no singular ("unidade", "fatia", "colher de sopa"). O app pluraliza
    # na hora de exibir ("2 unidades") — não guardamos o plural aqui.
    label: Mapped[str] = mapped_column(String(50))
    grams: Mapped[float] = mapped_column(Float)  # gramas de UMA unidade
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
