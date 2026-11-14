from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from uuid import uuid4

from app.db.session import get_db
from app.models.parcel import Parcel
from app.models.user import User
from app.schemas.domain import (
    OwnershipHistoryCreate, OwnershipHistoryOut, ParcelCreate, ParcelLocationReview,
    ParcelLocationSubmissionCreate, ParcelLocationSubmissionOut, ParcelOut, ParcelUpdate,
    ParcelPage, TransactionOut,
)
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import serialize_history, serialize_parcel, serialize_transaction
from app.models.ownership_history import OwnershipHistory
from app.models.transaction import Transaction
from app.models.parcel_location_submission import ParcelLocationSubmission
from app.models.owner import Owner

router = APIRouter(prefix="/parcels", tags=["Parcels"])
write_roles = require_roles("ADMIN", "OFFICER")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.get("", response_model=list[ParcelOut] | ParcelPage)
def list_parcels(
    q: str | None = Query(default=None),
    parcel_code: str | None = Query(default=None),
    upi: str | None = Query(default=None),
    owner_name: str | None = Query(default=None),
    province: str | None = Query(default=None),
    district: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="parcel_code", pattern="^(parcel_code|created_at|status|area_ha)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    latest_history = (
        db.query(
            OwnershipHistory.parcel_id,
            func.max(OwnershipHistory.id).label("latest_history_id"),
        )
        .group_by(OwnershipHistory.parcel_id)
        .subquery()
    )
    query = (
        db.query(Parcel)
        .outerjoin(latest_history, latest_history.c.parcel_id == Parcel.id)
        .outerjoin(
            OwnershipHistory,
            OwnershipHistory.id == latest_history.c.latest_history_id,
        )
        .outerjoin(Owner, Owner.id == OwnershipHistory.new_owner_id)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Parcel.parcel_code.ilike(like),
                Parcel.upi.ilike(like),
                Parcel.location.ilike(like),
                Owner.full_name.ilike(like),
            )
        )
    for column, value in (
        (Parcel.parcel_code, parcel_code),
        (Parcel.upi, upi),
        (Parcel.province, province),
        (Parcel.district, district),
        (Parcel.sector, sector),
        (Parcel.status, status_filter),
    ):
        if value:
            query = query.filter(column.ilike(f"%{value}%"))
    if owner_name:
        query = query.filter(Owner.full_name.ilike(f"%{owner_name}%"))

    sort_column = {
        "parcel_code": Parcel.parcel_code,
        "created_at": Parcel.created_at,
        "status": Parcel.status,
        "area_ha": Parcel.area_ha,
    }[sort_by]
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
    if page is None:
        return [serialize_parcel(db, item) for item in query.all()]

    total = query.order_by(None).with_entities(func.count(func.distinct(Parcel.id))).scalar() or 0
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, (total + page_size - 1) // page_size)
    return ParcelPage(
        items=[serialize_parcel(db, item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("", response_model=ParcelOut, status_code=status.HTTP_201_CREATED)
def create_parcel(
    payload: ParcelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    if db.query(Parcel).filter(Parcel.parcel_code == payload.parcel_code).first():
        raise HTTPException(status_code=400, detail="Parcel code already exists")
    if payload.upi and db.query(Parcel).filter(Parcel.upi == payload.upi).first():
        raise HTTPException(status_code=400, detail="UPI already exists")
    owner_payload = payload.owner
    owner = db.query(Owner).filter(
        Owner.identification_number == owner_payload.identification_number
    ).first()
    if owner is None and owner_payload.registration_number:
        owner = db.query(Owner).filter(
            Owner.registration_number == owner_payload.registration_number
        ).first()
    if owner is not None:
        if owner.owner_type != owner_payload.owner_type:
            raise HTTPException(status_code=409, detail="Owner identifier belongs to a different owner type")
    else:
        owner = Owner(
            owner_code=f"OWN-{uuid4().hex[:16].upper()}",
            full_name=owner_payload.full_name.strip(),
            owner_type=owner_payload.owner_type,
            identification_number=owner_payload.identification_number.strip(),
            phone=owner_payload.phone.strip() if owner_payload.phone else None,
            email=owner_payload.email.strip().lower() if owner_payload.email else None,
            organization_name=owner_payload.organization_name.strip() if owner_payload.organization_name else None,
            registration_number=owner_payload.registration_number.strip() if owner_payload.registration_number else None,
            status="ACTIVE",
        )
        db.add(owner)
        db.flush()

    parcel = Parcel(**payload.model_dump(exclude={"owner"}))
    db.add(parcel)
    db.flush()
    db.add(OwnershipHistory(
        parcel_id=parcel.id,
        previous_owner_id=None,
        new_owner_id=owner.id,
        transfer_date=datetime.utcnow(),
        reason_type="FIRST_REGISTRATION",
        supporting_reference=parcel.registration_reference,
    ))
    record_audit(db, action="PARCEL_CREATED", entity="Parcel", entity_id=parcel.parcel_code, user_id=current_user.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parcel could not be saved because it conflicts with an existing record.",
        ) from exc
    db.refresh(parcel)

    # Notify administrators and the registered landowner about the new parcel registration.
    from app.services.notification.service import get_admin_recipient_ids, get_user_recipient_id_by_email, notify_users

    recipient_ids: list[int] = list(get_admin_recipient_ids(db))
    owner_user_id = get_user_recipient_id_by_email(db, owner.email)
    if owner_user_id is not None and owner_user_id not in recipient_ids:
        recipient_ids.append(owner_user_id)
    notify_users(
        db,
        recipient_user_ids=recipient_ids,
        event_type="PARCEL_REGISTERED",
        title="New Parcel Registered",
        description="A new land parcel has been registered in the system.",
        priority="low",
        related_parcel_upi=parcel.upi,
    )

    return serialize_parcel(db, parcel)


@router.get("/{parcel_id}", response_model=ParcelOut)
def get_parcel(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return serialize_parcel(db, parcel)


@router.get("/upi/{upi}", response_model=ParcelOut)
def get_parcel_by_upi(upi: str, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    parcel = db.query(Parcel).filter(Parcel.upi == upi).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return serialize_parcel(db, parcel)


@router.get("/location-submissions", response_model=list[ParcelLocationSubmissionOut])
def list_location_submissions(
    status_filter: str = Query(default="PENDING_VERIFICATION", alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN")),
):
    return (
        db.query(ParcelLocationSubmission)
        .filter(ParcelLocationSubmission.status == status_filter)
        .order_by(ParcelLocationSubmission.submitted_at.desc())
        .all()
    )


@router.post("/{parcel_id}/location-submissions", response_model=ParcelLocationSubmissionOut, status_code=status.HTTP_201_CREATED)
def submit_parcel_location(
    parcel_id: int,
    payload: ParcelLocationSubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("OFFICER")),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    submission = ParcelLocationSubmission(
        parcel_id=parcel.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        boundary_geometry=payload.boundary_geometry,
        source=payload.source,
        submission_metadata=payload.metadata,
        status="PENDING_VERIFICATION",
        submitted_by=current_user.id,
        submitted_at=datetime.utcnow(),
    )
    db.add(submission)
    record_audit(
        db, action="PARCEL_LOCATION_SUBMITTED", entity="ParcelLocationSubmission",
        entity_id=parcel.parcel_code, user_id=current_user.id,
        metadata={"source": payload.source, "status": submission.status},
    )
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{parcel_id}/location-submissions", response_model=list[ParcelLocationSubmissionOut])
def list_parcel_location_submissions(
    parcel_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    return (
        db.query(ParcelLocationSubmission)
        .filter(ParcelLocationSubmission.parcel_id == parcel_id)
        .order_by(ParcelLocationSubmission.submitted_at.desc())
        .all()
    )


@router.put("/location-submissions/{submission_id}/review", response_model=ParcelLocationSubmissionOut)
def review_parcel_location(
    submission_id: int,
    payload: ParcelLocationReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    submission = db.query(ParcelLocationSubmission).filter(ParcelLocationSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Location submission not found")
    if submission.status != "PENDING_VERIFICATION":
        raise HTTPException(status_code=409, detail="Location submission has already been reviewed")
    if payload.decision == "REJECTED" and not payload.review_notes:
        raise HTTPException(status_code=400, detail="A rejection reason is required")

    parcel = db.query(Parcel).filter(Parcel.id == submission.parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    now = datetime.utcnow()
    submission.status = payload.decision
    submission.reviewed_by = current_user.id
    submission.reviewed_at = now
    submission.review_notes = payload.review_notes
    if payload.decision == "VERIFIED":
        parcel.latitude = submission.latitude
        parcel.longitude = submission.longitude
        parcel.boundary_geometry = submission.boundary_geometry
        parcel.location_data_source = submission.source
        parcel.location_verification_status = "VERIFIED"
        parcel.location_verification_metadata = submission.submission_metadata
        parcel.location_submitted_by = submission.submitted_by
        parcel.location_submitted_at = submission.submitted_at
        parcel.location_verified_by = current_user.id
        parcel.location_verified_at = now
    record_audit(
        db, action=f"PARCEL_LOCATION_{payload.decision}", entity="ParcelLocationSubmission",
        entity_id=str(submission.id), user_id=current_user.id,
        metadata={"parcel_id": parcel.id, "source": submission.source},
        details=payload.review_notes,
    )
    db.commit()
    db.refresh(submission)
    return submission


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


@router.get("/upi/{upi}/ownership-history", response_model=list[OwnershipHistoryOut])
def list_ownership_history_by_upi(upi: str, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    parcel = db.query(Parcel).filter(Parcel.upi == upi).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    rows = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel.id)
        .order_by(OwnershipHistory.transfer_date.asc())
        .all()
    )
    return [serialize_history(db, item) for item in rows]


@router.post(
    "/{parcel_id}/ownership-history",
    response_model=OwnershipHistoryOut,
    status_code=status.HTTP_403_FORBIDDEN,
)
def add_ownership_history(
    parcel_id: int,
    payload: OwnershipHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """Prevent direct history writes outside a completed transaction."""
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    raise HTTPException(
        status_code=403,
        detail=(
            "Ownership history can only be appended by completing an "
            "approved transaction."
        ),
    )


@router.get("/{parcel_id}/transactions", response_model=list[TransactionOut])
def list_parcel_transactions(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Parcel).filter(Parcel.id == parcel_id).first():
        raise HTTPException(status_code=404, detail="Parcel not found")
    rows = db.query(Transaction).filter(Transaction.parcel_id == parcel_id).order_by(Transaction.transaction_date.desc()).all()
    return [serialize_transaction(db, item) for item in rows]
