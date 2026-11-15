from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    __table_args__ = (
        CheckConstraint(
            "frequency IN ('instant', 'daily', 'weekly')",
            name="ck_notification_preferences_frequency",
        ),
    )

    # One preferences record per user.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    email_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    frequency: Mapped[str] = mapped_column(
        String(20), default="instant", nullable=False
    )