from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

SUBDIVISION_STATUSES = (
    "PENDING",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "COMPLETED",
)


class Subdivision(Base):
    __tablename__ = "subdivisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subdivision_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    parent_parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"), nullable=False, index=True)
    new_parcel_id: Mapped[int | None] = mapped_column(ForeignKey("parcels.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    area_ha: Mapped[float] = mapped_column(nullable=False)
    supporting_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    parent_parcel: Mapped["Parcel"] = relationship(foreign_keys=[parent_parcel_id])
    new_parcel: Mapped["Parcel"] = relationship(foreign_keys=[new_parcel_id])
