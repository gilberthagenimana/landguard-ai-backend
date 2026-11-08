from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.transaction_status import TransactionStatus
from app.db.base import Base

TRANSACTION_STATUSES = (
    "PENDING_REVIEW",
    "PENDING",
    "UNDER_REVIEW",
    "AWAITING_EVIDENCE",
    "FLAGGED",
    "VERIFIED",
    "APPROVED",
    "REJECTED",
    "COMPLETED",
)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    seller_owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True)
    buyer_owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    declared_value: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=2), nullable=True)
    supporting_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=TransactionStatus.PENDING_REVIEW.value,
        nullable=False,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    is_disposable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    parcel: Mapped["Parcel"] = relationship(back_populates="transactions")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="transaction")
