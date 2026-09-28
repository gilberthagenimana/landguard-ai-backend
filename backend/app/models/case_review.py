from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


CASE_STATUSES = (
    "OPEN",
    "UNDER_REVIEW",
    "NEEDS_INFORMATION",
    "RESOLVED",
    "CLOSED",
)


class CaseReview(Base):
    __tablename__ = "case_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    case_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", index=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
