
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            name="uq_notification_deliveries_notification_id",
        ),
        CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed')",
            name="ck_notification_deliveries_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )

    recipient_email: Mapped[str] = mapped_column(
        String(320), nullable=False
    )

    subject: Mapped[str] = mapped_column(
        String(200), nullable=False
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )

    # A lease identifier used to prevent an expired worker from updating a
    # delivery after another worker has reclaimed it.
    claim_token: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )

    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
