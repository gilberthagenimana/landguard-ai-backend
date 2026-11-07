from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import get_db
from app.models.case_review import CaseReview, CaseStatusHistory
from app.models.evidence import Evidence, EvidenceReviewHistory

from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction, TRANSACTION_STATUSES
from app.models.transaction_status_history import TransactionStatusHistory
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.schemas.domain import TransactionCreate, TransactionOut
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import next_transaction_code, serialize_transaction
from app.core.transaction_status import TransactionStatus

router = APIRouter(prefix="/transactions", tags=["Transactions"])
write_roles = require_roles("ADMIN", "OFFICER")
registration_roles = require_roles("OFFICER")
delete_roles = require_roles("ADMIN")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")



class TransactionStatusUpdate(BaseModel):
    status: str
    reason: str | None = None


class TransactionDeletionRequest(BaseModel):
    reason: str


VALID_STATUS_TRANSITIONS = {
    "PENDING": ["UNDER_REVIEW", "FLAGGED", "REJECTED"],
    "UNDER_REVIEW": ["FLAGGED", "APPROVED", "REJECTED"],
    "FLAGGED": ["UNDER_REVIEW", "REJECTED"],
    "APPROVED": ["COMPLETED"],
    "REJECTED": [],
    "COMPLETED": [],
}


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(Transaction)
    if q:
        like = f"%{q}%"
        query = query.filter(Transaction.transaction_code.ilike(like))
    if status_filter:
        query = query.filter(Transaction.status == status_filter)
    return [serialize_transaction(db, item) for item in query.order_by(Transaction.created_at.desc()).all()]


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(registration_roles),
):
    parcel = db.query(Parcel).filter(Parcel.id == payload.parcel_id).with_for_update().first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.status.upper() != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active parcels can receive transactions")
    if parcel.has_pending_transaction or db.query(Transaction).filter(
        Transaction.parcel_id == parcel.id,
        Transaction.status.in_(["PENDING", "UNDER_REVIEW", "FLAGGED", "APPROVED"]),
    ).first():
        raise HTTPException(status_code=409, detail="Parcel already has an incompatible pending transaction")

    if payload.seller_owner_id is not None and not db.query(Owner).filter(
        Owner.id == payload.seller_owner_id
    ).first():
        raise HTTPException(status_code=404, detail="Seller not found")

    latest_ownership = db.query(OwnershipHistory).filter(
        OwnershipHistory.parcel_id == parcel.id
    ).order_by(
        OwnershipHistory.transfer_date.desc(),
        OwnershipHistory.id.desc(),
    ).first()
    if not latest_ownership or not latest_ownership.new_owner_id:
        raise HTTPException(status_code=409, detail="Parcel has no valid current registered owner")
    seller_owner_id = latest_ownership.new_owner_id
    if payload.seller_owner_id is not None and payload.seller_owner_id != seller_owner_id:
        raise HTTPException(status_code=400, detail="Seller is determined by the parcel's current ownership record")

    buyer = db.query(Owner).filter(Owner.id == payload.buyer_owner_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    if buyer.status.upper() != "ACTIVE":
        raise HTTPException(status_code=409, detail="Buyer must be an active owner")
    if seller_owner_id == buyer.id:
        raise HTTPException(
            status_code=400,
            detail="Seller and buyer cannot be the same person",
        )

    item = Transaction(
        transaction_code=next_transaction_code(db),
        created_by=current_user.id,
        status=TransactionStatus.PENDING.value,
        parcel_id=parcel.id,
        seller_owner_id=seller_owner_id,
        buyer_owner_id=buyer.id,
        transaction_type=payload.transaction_type,
        transaction_date=payload.transaction_date,
        declared_value=payload.declared_value,
        supporting_reference=payload.supporting_reference,
    )
    db.add(item)
    db.flush()

    # Update parcel's has_pending_transaction flag
    if item.status == "PENDING":
        parcel.has_pending_transaction = True
        db.flush()

    record_audit(
        db,
        action="TRANSACTION_CREATED",
        entity="Transaction",
        entity_id=item.transaction_code,
        user_id=current_user.id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction could not be saved because a related record is invalid or already exists.",
        ) from exc
    db.refresh(item)
    return serialize_transaction(db, item)


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return serialize_transaction(db, item)


@router.get("/{transaction_id}/verification")
def get_stored_verification(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Transaction).filter(Transaction.id == transaction_id).first():
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(VerificationResultRecord)
        .filter(VerificationResultRecord.transaction_id == transaction_id)
        .order_by(VerificationResultRecord.id)
        .all()
    )
    return [
        {
            "rule_name": row.rule_name,
            "status": row.result,
            "severity": row.severity,
            "explanation": row.explanation,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.put("/{transaction_id}/status", response_model=TransactionOut)
def update_transaction_status(
    transaction_id: int,
    payload: TransactionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """Update transaction status with proper authorization and validation."""
    if payload.status not in TRANSACTION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(TRANSACTION_STATUSES)}")

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    current_status = transaction.status
    if current_status == payload.status:
        raise HTTPException(status_code=400, detail="Transaction is already in this status")

    allowed_transitions = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if payload.status not in allowed_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status} to {payload.status}. Allowed: {', '.join(allowed_transitions)}"
        )

    parcel_query = db.query(Parcel).filter(Parcel.id == transaction.parcel_id)
    if payload.status == "COMPLETED":
        parcel_query = parcel_query.with_for_update()
    parcel = parcel_query.first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    ownership_entry = None

    if payload.status == "COMPLETED":
        if current_status != "APPROVED":
            raise HTTPException(
                status_code=400,
                detail="Only approved transactions can complete ownership transfers.",
            )

        if not transaction.seller_owner_id or not transaction.buyer_owner_id:
            raise HTTPException(
                status_code=409,
                detail="Transfer requires both a seller and a buyer.",
            )

        buyer = db.query(Owner).filter(
            Owner.id == transaction.buyer_owner_id
        ).first()
        if not buyer:
            raise HTTPException(status_code=409, detail="Transfer buyer was not found.")

        latest_ownership = (
            db.query(OwnershipHistory)
            .filter(OwnershipHistory.parcel_id == transaction.parcel_id)
            .order_by(
                OwnershipHistory.transfer_date.desc(),
                OwnershipHistory.id.desc(),
            )
            .first()
        )

        if latest_ownership is None or latest_ownership.new_owner_id is None:
            raise HTTPException(
                status_code=409,
                detail="Cannot complete transfer: current recorded ownership is not established.",
            )

        if latest_ownership.new_owner_id != transaction.seller_owner_id:
            raise HTTPException(
                status_code=409,
                detail="Cannot complete transfer: seller does not match the latest recorded owner.",
            )

        ownership_entry = OwnershipHistory(
            parcel_id=transaction.parcel_id,
            previous_owner_id=transaction.seller_owner_id,
            new_owner_id=transaction.buyer_owner_id,
            transfer_date=datetime.utcnow(),
            reason_type="TRANSFER",
            supporting_reference=transaction.transaction_code,
        )

    # Persist status and its history in the same transaction.
    transaction.status = payload.status
    db.flush()

    if ownership_entry is not None:
        db.add(ownership_entry)
        db.flush()

    # Record status history
    status_history = TransactionStatusHistory(
        transaction_id=transaction.id,
        previous_status=current_status,
        new_status=payload.status,
        changed_by=current_user.id,
        reason=payload.reason,
    )
    db.add(status_history)

    # Update parcel's has_pending_transaction flag
    if parcel:
        has_pending = (
            db.query(Transaction)
            .filter(
                Transaction.parcel_id == transaction.parcel_id,
                Transaction.status.in_(["PENDING", "UNDER_REVIEW", "FLAGGED"]),
            )
            .first()
        ) is not None
        parcel.has_pending_transaction = has_pending
        db.flush()

    record_audit(
        db,
        action="TRANSACTION_STATUS_CHANGED",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={"from": current_status, "to": payload.status, "reason": payload.reason},
    )
    db.commit()
    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.get("/{transaction_id}/status-history")
def get_transaction_status_history(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Transaction).filter(Transaction.id == transaction_id).first():
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(TransactionStatusHistory)
        .filter(TransactionStatusHistory.transaction_id == transaction_id)
        .order_by(TransactionStatusHistory.created_at.desc())
        .all()
    )
    return [
        {
            "previous_status": row.previous_status,
            "new_status": row.new_status,
            "changed_by": row.changed_by,
            "reason": row.reason,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/{transaction_id}/archive", response_model=TransactionOut)
def archive_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(delete_roles),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction is already archived")

    transaction.is_archived = True
    transaction.archived_at = datetime.utcnow()
    transaction.archived_by = current_user.id
    record_audit(
        db,
        action="TRANSACTION_ARCHIVED",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={"reason": "Transaction archived by authorized administrator"},
    )
    db.commit()
    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    payload: TransactionDeletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(delete_roles),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A deletion reason is required.",
        )
    if transaction.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed transactions cannot be permanently deleted. Archive this transaction instead.",
        )

    parcel_id = transaction.parcel_id
    transaction_code = transaction.transaction_code

    try:
        evidence_ids = [
            evidence_id
            for evidence_id, in db.query(Evidence.id)
            .filter(Evidence.transaction_id == transaction_id)
            .all()
        ]
        if evidence_ids:
            db.query(EvidenceReviewHistory).filter(
                EvidenceReviewHistory.evidence_id.in_(evidence_ids)
            ).delete(synchronize_session=False)
        db.query(Evidence).filter(
            Evidence.transaction_id == transaction_id
        ).delete(synchronize_session=False)

        case_ids = [
            case_id
            for case_id, in db.query(CaseReview.id)
            .filter(CaseReview.transaction_id == transaction_id)
            .all()
        ]
        if case_ids:
            db.query(CaseStatusHistory).filter(
                CaseStatusHistory.case_id.in_(case_ids)
            ).delete(synchronize_session=False)
        db.query(CaseReview).filter(
            CaseReview.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(RiskPrediction).filter(
            RiskPrediction.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(TransactionStatusHistory).filter(
            TransactionStatusHistory.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(VerificationResultRecord).filter(
            VerificationResultRecord.transaction_id == transaction_id
        ).delete(synchronize_session=False)

        db.delete(transaction)
        db.flush()

        parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
        if parcel:
            parcel.has_pending_transaction = db.query(Transaction).filter(
                Transaction.parcel_id == parcel_id,
                Transaction.status.in_(["PENDING", "UNDER_REVIEW", "FLAGGED"]),
            ).first() is not None

        record_audit(
            db,
            action="TRANSACTION_DELETED",
            entity="Transaction",
            entity_id=transaction_code,
            user_id=current_user.id,
            metadata={
                "reason": reason,
                "deletion_policy": "ADMIN_CONFIRMED_NON_COMPLETED_TRANSACTION",
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction cannot be deleted because related records are still protected.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction deletion failed and all changes were rolled back.",
        ) from exc
