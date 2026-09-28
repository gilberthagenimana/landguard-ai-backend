from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parcel_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False, default="Kigali")
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    sector: Mapped[str] = mapped_column(String(120), nullable=False)
    cell: Mapped[str] = mapped_column(String(120), nullable=False)
    village: Mapped[str] = mapped_column(String(120), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
    registration_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    ownership_history: Mapped[list["OwnershipHistory"]] = relationship(back_populates="parcel")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="parcel")
