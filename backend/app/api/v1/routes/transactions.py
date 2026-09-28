from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.owner import Owner
from app.models.parcel import Parcel
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.schemas.domain import TransactionCreate, TransactionOut
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import next_transaction_code, serialize_transaction

router = APIRouter(prefix="/transactions", tags=["Transactions"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(Transaction)
    if q:
        like = f"%{q}%"
        query = query.filter(Transaction.transaction_code.ilike(like))
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
    item = Transaction(transaction_code=next_transaction_code(db), created_by=current_user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    record_audit(db, action="TRANSACTION_CREATED", entity="Transaction", entity_id=item.transaction_code, user_id=current_user.id)
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
