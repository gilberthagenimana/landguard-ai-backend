from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvidenceType(StrEnum):
    SALE_AGREEMENT = "SALE_AGREEMENT"
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    OWNERSHIP_PROOF = "OWNERSHIP_PROOF"
    SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT"


class EvidenceStatus(StrEnum):
    NOT_PROVIDED = "NOT_PROVIDED"
    UPLOADED = "UPLOADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED_FOR_REVIEW = "VERIFIED_FOR_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INCONSISTENT = "INCONSISTENT"


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=EvidenceStatus.UPLOADED.value, index=True)
    stated_payment_amount: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stated_payment_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    transaction = relationship("Transaction", back_populates="evidence")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    review_history = relationship("EvidenceReviewHistory", back_populates="evidence")


class EvidenceReviewHistory(Base):
    __tablename__ = "evidence_review_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    evidence = relationship("Evidence", back_populates="review_history")
