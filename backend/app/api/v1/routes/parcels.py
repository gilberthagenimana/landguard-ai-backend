from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parcel import Parcel
from app.models.user import User
from app.schemas.domain import OwnershipHistoryCreate, OwnershipHistoryOut, ParcelCreate, ParcelOut, ParcelUpdate, TransactionOut
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import serialize_history, serialize_parcel, serialize_transaction
from app.models.ownership_history import OwnershipHistory
from app.models.transaction import Transaction

router = APIRouter(prefix="/parcels", tags=["Parcels"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.get("", response_model=list[ParcelOut])
def list_parcels(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(Parcel)
    if q:
        like = f"%{q}%"
        query = query.filter((Parcel.parcel_code.ilike(like)) | (Parcel.location.ilike(like)) | (Parcel.district.ilike(like)))
    return [serialize_parcel(db, item) for item in query.order_by(Parcel.parcel_code).all()]


@router.post("", response_model=ParcelOut, status_code=status.HTTP_201_CREATED)
def create_parcel(
    payload: ParcelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    if db.query(Parcel).filter(Parcel.parcel_code == payload.parcel_code).first():
        raise HTTPException(status_code=400, detail="Parcel code already exists")
    parcel = Parcel(**payload.model_dump())
    db.add(parcel)
    db.flush()
    record_audit(db, action="PARCEL_CREATED", entity="Parcel", entity_id=parcel.parcel_code, user_id=current_user.id)
    db.commit()
    db.refresh(parcel)
    return serialize_parcel(db, parcel)


@router.get("/{parcel_id}", response_model=ParcelOut)
def get_parcel(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return serialize_parcel(db, parcel)


@router.put("/{parcel_id}", response_model=ParcelOut)
def update_parcel(
    parcel_id: int,
    payload: ParcelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(parcel, field, value)
    record_audit(db, action="PARCEL_UPDATED", entity="Parcel", entity_id=parcel.parcel_code, user_id=current_user.id)
    db.commit()
    db.refresh(parcel)
    return serialize_parcel(db, parcel)


@router.get("/{parcel_id}/ownership-history", response_model=list[OwnershipHistoryOut])
def list_ownership_history(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    rows = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel_id)
        .order_by(OwnershipHistory.transfer_date.asc())
        .all()
    )
    return [serialize_history(db, item) for item in rows]


@router.post("/{parcel_id}/ownership-history", response_model=OwnershipHistoryOut, status_code=status.HTTP_201_CREATED)
def add_ownership_history(
    parcel_id: int,
    payload: OwnershipHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    item = OwnershipHistory(parcel_id=parcel_id, **payload.model_dump())
    db.add(item)
    db.flush()
    record_audit(db, action="OWNERSHIP_UPDATED", entity="Parcel", entity_id=str(parcel_id), user_id=current_user.id)
    db.commit()
    db.refresh(item)
    return serialize_history(db, item)


@router.get("/{parcel_id}/transactions", response_model=list[TransactionOut])
def list_parcel_transactions(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    rows = db.query(Transaction).filter(Transaction.parcel_id == parcel_id).order_by(Transaction.transaction_date.desc()).all()
    return [serialize_transaction(db, item) for item in rows]
