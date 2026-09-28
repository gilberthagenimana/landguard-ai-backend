from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    parcel: Mapped["Parcel"] = relationship(back_populates="transactions")
