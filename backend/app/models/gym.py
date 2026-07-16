"""Academia da pessoa + check-ins com prova de localização.

Serve ao desafio "quem vai mais à academia": a pessoa cadastra a academia dela
(buscada no mapa do OpenStreetMap) e, pra marcar que treinou, precisa estar COM
a localização ligada e perto dela. Um check-in feito longe ainda conta, mas fica
marcado como "fora" (transparência sem punir quem viajou).
"""

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Raio (metros) em que o check-in conta como "na sua academia". Folga suficiente
# pro GPS de celular (que erra dezenas de metros dentro de prédios) sem deixar
# alguém marcar de casa.
HOME_GYM_RADIUS_M = 250.0


class UserGym(Base):
    """A academia cadastrada da pessoa (uma por usuário)."""

    __tablename__ = "user_gyms"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    # id do ponto no OpenStreetMap (quando veio da busca) — só rastreabilidade
    osm_id: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GymCheckIn(Base):
    """Um check-in de treino num dia. Append-only (regra 4 do CLAUDE.md):
    um por dia por pessoa — a data é única, então não dá pra inflar o placar."""

    __tablename__ = "gym_checkins"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_gym_checkin_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    day: Mapped[date] = mapped_column(Date, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Onde a pessoa estava quando marcou (a "prova").
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)

    # Estava perto da academia cadastrada? Se não, conta mas fica marcado "fora".
    at_home_gym: Mapped[bool] = mapped_column(Boolean, default=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Nome informado quando treinou em outro lugar ("treinei em outra academia").
    gym_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
