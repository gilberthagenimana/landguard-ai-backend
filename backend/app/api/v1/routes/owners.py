from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.owner import Owner
from app.models.user import User
from app.schemas.domain import OwnerCreate, OwnerOut, OwnerUpdate
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import serialize_owner

router = APIRouter(prefix="/owners", tags=["Owners"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.get("", response_model=list[OwnerOut])
def list_owners(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(Owner)
    if q:
        like = f"%{q}%"
        query = query.filter((Owner.full_name.ilike(like)) | (Owner.owner_code.ilike(like)))
    return [serialize_owner(db, item) for item in query.order_by(Owner.owner_code).all()]


@router.post("", response_model=OwnerOut, status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: OwnerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    if db.query(Owner).filter(Owner.owner_code == payload.owner_code).first():
        raise HTTPException(status_code=400, detail="Owner code already exists")
    owner = Owner(**payload.model_dump())
    db.add(owner)
    db.flush()
    record_audit(db, action="OWNER_CREATED", entity="Owner", entity_id=owner.owner_code, user_id=current_user.id)
    db.commit()
    db.refresh(owner)
    return serialize_owner(db, owner)


@router.get("/{owner_id}", response_model=OwnerOut)
def get_owner(owner_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return serialize_owner(db, owner)


@router.put("/{owner_id}", response_model=OwnerOut)
def update_owner(
    owner_id: int,
    payload: OwnerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(owner, field, value)
    record_audit(db, action="OWNER_UPDATED", entity="Owner", entity_id=owner.owner_code, user_id=current_user.id)
    db.commit()
    db.refresh(owner)
    return serialize_owner(db, owner)
