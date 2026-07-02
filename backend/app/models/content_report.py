import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ReportTargetType(str, enum.Enum):
    USER = "user"
    FEED_POST = "feed_post"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"


class ContentReport(Base):
    """Denúncia de usuário ou post. Canal de denúncia com resposta humana
    (espec. 3.5) — fica pendente até alguém do time revisar; não há
    moderação automática de imagem nesta fase (dependeria de um serviço de
    moderação dedicado, e não pode usar a IA do app pois isso violaria a
    regra de IA exclusiva do Pro para uma feature de segurança que precisa
    valer para todo mundo)."""

    __tablename__ = "content_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[ReportTargetType] = mapped_column(
        Enum(ReportTargetType, name="report_target_type")
    )
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status"), default=ReportStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
