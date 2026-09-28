from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OwnershipHistory(Base):
    __tablename__ = "ownership_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    previous_owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True)
    new_owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id"), nullable=True)
    transfer_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reason_type: Mapped[str] = mapped_column(String(100), default="TRANSFER")
    supporting_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    parcel: Mapped["Parcel"] = relationship(back_populates="ownership_history")
