from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VerificationResultRecord(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
