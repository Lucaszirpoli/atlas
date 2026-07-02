import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MeasurementType(str, enum.Enum):
    WAIST = "waist"
    HIP = "hip"
    CHEST = "chest"
    ARM_LEFT = "arm_left"
    ARM_RIGHT = "arm_right"
    THIGH_LEFT = "thigh_left"
    THIGH_RIGHT = "thigh_right"
    NECK = "neck"


class BodyMeasurement(Base):
    """Medida corporal (cm), append-only — base do gráfico comparativo por
    data mencionado na seção 3.2/3.8."""

    __tablename__ = "body_measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[MeasurementType] = mapped_column(Enum(MeasurementType, name="measurement_type"))
    value_cm: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProgressPhoto(Base):
    """Metadado de foto de progresso corporal. O upload do binário em si vai
    para storage S3-compatible (Cloudflare R2); aqui guardamos só a URL
    resultante e a data — o histórico também é append-only, fotos nunca são
    substituídas, só uma nova é adicionada à timeline."""

    __tablename__ = "progress_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    photo_url: Mapped[str] = mapped_column(String(500))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
