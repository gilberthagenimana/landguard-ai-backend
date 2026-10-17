"""Evidence management service for transaction supporting documents."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.evidence import Evidence, EvidenceReviewHistory, EvidenceStatus, EvidenceType
from app.models.transaction import Transaction
from app.models.user import User

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (default, overridden by settings)


class EvidenceError(Exception):
    """Base exception for evidence operations."""


class InvalidFileType(EvidenceError):
    """File type not allowed."""


class FileTooLarge(EvidenceError):
    """File exceeds size limit."""


class StorageError(EvidenceError):
    """File storage operation failed."""


def _storage_path() -> Path:
    """Get the evidence storage directory."""
    configured = Path(settings.evidence_storage_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[4] / configured


def _max_file_size() -> int:
    """Get the maximum allowed file size in bytes."""
    return settings.max_evidence_file_size


def _validate_file(file: UploadFile) -> None:
    """Validate file type and size."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileType(
            f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise InvalidFileType(
            f"MIME type '{content_type}' not allowed. Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
        )


def _compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def _generate_storage_filename(original_filename: str) -> str:
    """Generate a safe storage filename."""
    ext = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def store_evidence_file(
    db: Session,
    transaction: Transaction,
    uploader: User,
    file: UploadFile,
    document_type: str,
    stated_payment_amount: str | None = None,
    stated_payment_date: datetime | None = None,
    payment_reference: str | None = None,
    notes: str | None = None,
) -> Evidence:
    """Store an evidence file and create database record."""
    _validate_file(file)

    content = file.file.read()
    file_size = len(content)

    max_size = _max_file_size()
    if file_size > max_size:
        raise FileTooLarge(f"File size {file_size} exceeds limit of {max_size}")

    if file_size == 0:
        raise EvidenceError("Empty file")

    file_hash = _compute_file_hash(content)
    storage_filename = _generate_storage_filename(file.filename or "document")

    storage_dir = _storage_path()
    storage_dir.mkdir(parents=True, exist_ok=True)

    storage_path = storage_dir / storage_filename

    try:
        with open(storage_path, "wb") as f:
            f.write(content)
    except OSError as exc:
        raise StorageError(f"Failed to store file: {exc}") from exc

    evidence = Evidence(
        transaction_id=transaction.id,
        uploaded_by=uploader.id,
        document_type=document_type,
        original_filename=file.filename or "document",
        storage_filename=storage_filename,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        file_hash=file_hash,
        status=EvidenceStatus.UPLOADED.value,
        stated_payment_amount=stated_payment_amount,
        stated_payment_date=stated_payment_date,
        payment_reference=payment_reference,
        notes=notes,
    )
    db.add(evidence)
    db.flush()

    # Record review history
    history = EvidenceReviewHistory(
        evidence_id=evidence.id,
        previous_status=None,
        new_status=EvidenceStatus.UPLOADED.value,
        changed_by=uploader.id,
        reason="Evidence uploaded",
    )
    db.add(history)

    db.commit()
    db.refresh(evidence)
    return evidence


def get_evidence_file_path(evidence: Evidence) -> Path:
    """Get the storage path for an evidence file."""
    return _storage_path() / evidence.storage_filename


def review_evidence(
    db: Session,
    evidence: Evidence,
    reviewer: User,
    new_status: str,
    review_notes: str | None = None,
) -> Evidence:
    """Update evidence review status."""
    if new_status not in {status.value for status in EvidenceStatus}:
        raise EvidenceError(f"Invalid status: {new_status}")

    previous_status = evidence.status
    evidence.status = new_status
    evidence.reviewed_by = reviewer.id
    evidence.reviewed_at = datetime.utcnow()
    evidence.review_notes = review_notes

    history = EvidenceReviewHistory(
        evidence_id=evidence.id,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=reviewer.id,
        reason=review_notes,
    )
    db.add(history)
    db.commit()
    db.refresh(evidence)
    return evidence


def get_transaction_evidence(db: Session, transaction_id: int) -> list[Evidence]:
    """Get all evidence for a transaction."""
    return (
        db.query(Evidence)
        .filter(Evidence.transaction_id == transaction_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )


def get_evidence_or_404(db: Session, evidence_id: int) -> Evidence:
    """Get evidence by ID or raise exception."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise EvidenceError(f"Evidence not found: {evidence_id}")
    return evidence
