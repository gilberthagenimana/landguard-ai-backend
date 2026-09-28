from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicators: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
