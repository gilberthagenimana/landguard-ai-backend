from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
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
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


class TransactionStatusUpdate(BaseModel):
    status: str
    reason: str | None = None


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
    current_user: User = Depends(write_roles),
):
    if not db.query(Parcel).filter(Parcel.id == payload.parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    if payload.seller_owner_id and not db.query(Owner).filter(Owner.id == payload.seller_owner_id).first():
        raise HTTPException(status_code=404, detail="Seller not found")
    if payload.buyer_owner_id and not db.query(Owner).filter(Owner.id == payload.buyer_owner_id).first():
        raise HTTPException(status_code=404, detail="Buyer not found")

    if (
        payload.seller_owner_id
        and payload.buyer_owner_id
        and payload.seller_owner_id == payload.buyer_owner_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Seller and buyer cannot be the same person",
        )

    item = Transaction(
        transaction_code=next_transaction_code(db),
        created_by=current_user.id,
        status=TransactionStatus.PENDING.value,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()

    # Update parcel's has_pending_transaction flag
    parcel = db.query(Parcel).filter(Parcel.id == payload.parcel_id).first()
    if parcel and item.status == "PENDING":
        parcel.has_pending_transaction = True
        db.flush()

    record_audit(
        db,
        action="TRANSACTION_CREATED",
        entity="Transaction",
        entity_id=item.transaction_code,
        user_id=current_user.id,
    )
    db.commit()
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
