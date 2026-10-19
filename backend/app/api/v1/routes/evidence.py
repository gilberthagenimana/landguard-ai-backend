"""Evidence management API routes for transaction supporting documents."""
import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.evidence import Evidence, EvidenceReviewHistory, EvidenceStatus, EvidenceType
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.evidence import EvidenceOut, EvidenceReviewRequest, EvidenceReviewHistoryOut
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles

router = APIRouter(prefix="/evidence", tags=["Evidence"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


def _storage_path() -> Path:
    """Get the evidence storage directory."""
    configured = Path(settings.evidence_storage_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[4] / configured


def _validate_file(file: UploadFile) -> None:
    """Validate file type and size."""
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise InvalidFileType(
            f"File type '{ext}' not allowed. Allowed: .pdf, .jpg, .jpeg, .png"
        )

    content_type = file.content_type or ""
    if content_type not in {"application/pdf", "image/jpeg", "image/png"}:
        raise InvalidFileType(
            f"MIME type '{content_type}' not allowed. Allowed: application/pdf, image/jpeg, image/png"
        )


class InvalidFileType(Exception):
    """File type not allowed."""
    pass


@router.post("/transactions/{transaction_id}", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    transaction_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    stated_payment_amount: str | None = Form(default=None),
    payment_reference: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """Upload supporting evidence for a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Validate document type
    if document_type not in {dt.value for dt in EvidenceType}:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Must be one of: {', '.join(dt.value for dt in EvidenceType)}"
        )

    # Validate file
    try:
        _validate_file(file)
    except InvalidFileType as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Read and validate file size
    content = await file.read()
    file_size = len(content)

    max_size = settings.max_evidence_file_size
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file_size} exceeds limit of {max_size}"
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Compute hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Generate storage filename
    ext = Path(file.filename or "").suffix.lower()
    storage_filename = f"{uuid.uuid4().hex}{ext}"

    # Store file
    storage_dir = _storage_path()
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / storage_filename

    try:
        with open(storage_path, "wb") as f:
            f.write(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc

    # Create database record
    evidence = Evidence(
        transaction_id=transaction.id,
        document_type=document_type,
        original_filename=file.filename or "document",
        storage_filename=storage_filename,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        file_hash=file_hash,
        status=EvidenceStatus.UPLOADED.value,
        stated_payment_amount=stated_payment_amount,
        stated_payment_date=None,  # Would be extracted via OCR if implemented
        payment_reference=payment_reference,
        notes=notes,
        uploaded_by=current_user.id,
    )
    db.add(evidence)
    db.flush()

    # Record audit
    record_audit(
        db,
        action="EVIDENCE_UPLOADED",
        entity="Evidence",
        entity_id=str(evidence.id),
        user_id=current_user.id,
        metadata={"transaction_id": transaction_id, "document_type": document_type},
    )
    db.commit()
    db.refresh(evidence)

    return EvidenceOut(
        id=evidence.id,
        transaction_id=evidence.transaction_id,
        document_type=evidence.document_type,
        original_filename=evidence.original_filename,
        file_size=evidence.file_size,
        mime_type=evidence.mime_type,
        status=evidence.status,
        stated_payment_amount=evidence.stated_payment_amount,
        stated_payment_date=evidence.stated_payment_date,
        payment_reference=evidence.payment_reference,
        notes=evidence.notes,
        uploaded_by=evidence.uploaded_by,
        reviewed_by=evidence.reviewed_by,
        reviewed_at=evidence.reviewed_at,
        review_notes=evidence.review_notes,
        created_at=evidence.created_at,
        updated_at=evidence.updated_at,
    )


@router.get("/transactions/{transaction_id}", response_model=list[EvidenceOut])
def list_transaction_evidence(
    transaction_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    """List all evidence for a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    evidence_list = (
        db.query(Evidence)
        .filter(Evidence.transaction_id == transaction_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )
    return [
        EvidenceOut(
            id=e.id,
            transaction_id=e.transaction_id,
            document_type=e.document_type,
            original_filename=e.original_filename,
            file_size=e.file_size,
            mime_type=e.mime_type,
            status=e.status,
            stated_payment_amount=e.stated_payment_amount,
            stated_payment_date=e.stated_payment_date,
            payment_reference=e.payment_reference,
            notes=e.notes,
            uploaded_by=e.uploaded_by,
            reviewed_by=e.reviewed_by,
            reviewed_at=e.reviewed_at,
            review_notes=e.review_notes,
            created_at=e.created_at,
            updated_at=e.updated_at,
        )
        for e in evidence_list
    ]


@router.get("/{evidence_id}")
def download_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(read_roles),
):
    """Download an evidence file."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    file_path = _storage_path() / evidence.storage_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on storage")

    record_audit(
        db,
        action="EVIDENCE_DOWNLOADED",
        entity="Evidence",
        entity_id=str(evidence.id),
        user_id=current_user.id,
    )
    db.commit()

    return FileResponse(
        path=str(file_path),
        filename=evidence.original_filename,
        media_type=evidence.mime_type,
    )


@router.put("/{evidence_id}/review", response_model=EvidenceOut)
def review_evidence(
    evidence_id: int,
    payload: EvidenceReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """Review evidence and update status."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    if payload.status not in {status.value for status in EvidenceStatus}:
        raise HTTPException(status_code=400, detail="Invalid evidence status")

    previous_status = evidence.status
    evidence.status = payload.status
    evidence.reviewed_by = current_user.id
    evidence.reviewed_at = datetime.utcnow()
    evidence.review_notes = payload.review_notes

    history = EvidenceReviewHistory(
        evidence_id=evidence.id,
        previous_status=previous_status,
        new_status=payload.status,
        changed_by=current_user.id,
        reason=payload.review_notes,
    )
    db.add(history)

    record_audit(
        db,
        action="EVIDENCE_REVIEWED",
        entity="Evidence",
        entity_id=str(evidence.id),
        user_id=current_user.id,
        metadata={"new_status": payload.status},
    )
    db.commit()
    db.refresh(evidence)

    return EvidenceOut(
        id=evidence.id,
        transaction_id=evidence.transaction_id,
        document_type=evidence.document_type,
        original_filename=evidence.original_filename,
        file_size=evidence.file_size,
        mime_type=evidence.mime_type,
        status=evidence.status,
        stated_payment_amount=evidence.stated_payment_amount,
        stated_payment_date=evidence.stated_payment_date,
        payment_reference=evidence.payment_reference,
        notes=evidence.notes,
        uploaded_by=evidence.uploaded_by,
        reviewed_by=evidence.reviewed_by,
        reviewed_at=evidence.reviewed_at,
        review_notes=evidence.review_notes,
        created_at=evidence.created_at,
        updated_at=evidence.updated_at,
    )


@router.get("/{evidence_id}/review-history", response_model=list[EvidenceReviewHistoryOut])
def get_evidence_review_history(
    evidence_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    """Get review history for an evidence item."""
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    history = (
        db.query(EvidenceReviewHistory)
        .filter(EvidenceReviewHistory.evidence_id == evidence_id)
        .order_by(EvidenceReviewHistory.created_at.desc())
        .all()
    )
    return [
        EvidenceReviewHistoryOut(
            id=h.id,
            evidence_id=h.evidence_id,
            previous_status=h.previous_status,
            new_status=h.new_status,
            changed_by=h.changed_by,
            reason=h.reason,
            created_at=h.created_at,
        )
        for h in history
    ]
