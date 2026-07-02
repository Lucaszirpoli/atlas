import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FriendRequestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class FriendRequest(Base):
    """Pedido de amizade. Nunca segue automático — o destinatário precisa
    aceitar (espec. 3.5). status=accepted é a fonte da verdade de quem é
    amigo de quem."""

    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_request_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[FriendRequestStatus] = mapped_column(
        Enum(FriendRequestStatus, name="friend_request_status"), default=FriendRequestStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
