"""Evidence management API routes for transaction supporting documents."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.evidence import Evidence, EvidenceReviewHistory, EvidenceStatus
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.evidence import EvidenceOut, EvidenceReviewRequest, EvidenceReviewHistoryOut
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.evidence.service import (
    store_evidence_file,
    review_evidence as review_evidence_service,
    get_transaction_evidence,
    get_evidence_or_404,
    get_evidence_file_path,
    InvalidFileType,
    FileTooLarge,
    StorageError,
    EvidenceError,
)

router = APIRouter(prefix="/evidence", tags=["Evidence"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.post("/transactions/{transaction_id}", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    transaction_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    stated_payment_amount: str | None = Form(default=None),
    stated_payment_date: str | None = Form(default=None),
    payment_reference: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """Upload supporting evidence for a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    try:
        evidence = store_evidence_file(
            db=db,
            transaction=transaction,
            uploader=current_user,
            file=file,
            document_type=document_type,
            stated_payment_amount=stated_payment_amount,
            stated_payment_date=stated_payment_date,
            payment_reference=payment_reference,
            notes=notes,
        )
    except InvalidFileType as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLarge as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except EvidenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        db,
        action="EVIDENCE_UPLOADED",
        entity="Evidence",
        entity_id=str(evidence.id),
        user_id=current_user.id,
        metadata={"transaction_id": transaction_id, "document_type": document_type},
    )
    db.commit()

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

    evidence_list = get_transaction_evidence(db, transaction_id)
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
    evidence = get_evidence_or_404(db, evidence_id)
    file_path = get_evidence_file_path(evidence)

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
    evidence = get_evidence_or_404(db, evidence_id)

    try:
        evidence = review_evidence_service(
            db,
            evidence,
            current_user,
            payload.status,
            payload.review_notes,
        )
    except EvidenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        db,
        action="EVIDENCE_REVIEWED",
        entity="Evidence",
        entity_id=str(evidence.id),
        user_id=current_user.id,
        metadata={"new_status": payload.status},
    )
    db.commit()

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
    evidence = get_evidence_or_404(db, evidence_id)
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
