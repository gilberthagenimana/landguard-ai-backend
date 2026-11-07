from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Owner(Base):
    __tablename__ = "owners"
    __table_args__ = (
        Index(
            "ix_owners_identification_number_unique",
            "identification_number",
            unique=True,
        ),
        Index(
            "ix_owners_registration_number_unique",
            "registration_number",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="INDIVIDUAL",
    )
    identification_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
