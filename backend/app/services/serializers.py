from sqlalchemy.orm import Session

from app.models.case_review import CaseReview
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.domain import (
    AuditLogOut,
    CaseOut,
    OwnerOut,
    OwnershipHistoryOut,
    ParcelOut,
    TransactionOut,
)


def latest_owner(db: Session, parcel_id: int) -> Owner | None:
    history = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel_id)
        .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
        .first()
    )
    if not history or not history.new_owner_id:
        return None
    return db.query(Owner).filter(Owner.id == history.new_owner_id).first()


def owner_name(db: Session, owner_id: int | None) -> str | None:
    if not owner_id:
        return None
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    return owner.full_name if owner else None


def latest_risk(db: Session, transaction_id: int) -> RiskPrediction | None:
    return (
        db.query(RiskPrediction)
        .filter(RiskPrediction.transaction_id == transaction_id)
        .order_by(RiskPrediction.created_at.desc(), RiskPrediction.id.desc())
        .first()
    )


def serialize_parcel(db: Session, parcel: Parcel) -> ParcelOut:
    owner = latest_owner(db, parcel.id)
    return ParcelOut(
        id=parcel.id,
        parcel_code=parcel.parcel_code,
        location=parcel.location,
        province=parcel.province,
        district=parcel.district,
        sector=parcel.sector,
        cell=parcel.cell,
        village=parcel.village,
        area_ha=parcel.area_ha,
        status=parcel.status,
        registration_reference=parcel.registration_reference,
        created_at=parcel.created_at,
        updated_at=parcel.updated_at,
        current_owner_name=owner.full_name if owner else None,
        current_owner_id=owner.id if owner else None,
    )


def serialize_owner(db: Session, owner: Owner) -> OwnerOut:
    current_ids = []
    histories = db.query(OwnershipHistory).order_by(OwnershipHistory.transfer_date.desc()).all()
    seen = set()
    for item in histories:
        if item.parcel_id in seen:
            continue
        seen.add(item.parcel_id)
        if item.new_owner_id == owner.id:
            current_ids.append(item.parcel_id)
    return OwnerOut(
        id=owner.id,
        owner_code=owner.owner_code,
        full_name=owner.full_name,
        identification_number=owner.identification_number,
        phone=owner.phone,
        email=owner.email,
        status=owner.status,
        created_at=owner.created_at,
        updated_at=owner.updated_at,
        parcels_owned=len(current_ids),
    )


def serialize_history(db: Session, item: OwnershipHistory) -> OwnershipHistoryOut:
    return OwnershipHistoryOut(
        id=item.id,
        parcel_id=item.parcel_id,
        previous_owner_id=item.previous_owner_id,
        previous_owner_name=owner_name(db, item.previous_owner_id),
        new_owner_id=item.new_owner_id,
        new_owner_name=owner_name(db, item.new_owner_id),
        transfer_date=item.transfer_date,
        reason_type=item.reason_type,
        supporting_reference=item.supporting_reference,
        created_at=item.created_at,
    )


def serialize_transaction(db: Session, item: Transaction) -> TransactionOut:
    parcel = db.query(Parcel).filter(Parcel.id == item.parcel_id).first()
    risk = latest_risk(db, item.id)
    return TransactionOut(
        id=item.id,
        transaction_code=item.transaction_code,
        parcel_id=item.parcel_id,
        parcel_code=parcel.parcel_code if parcel else None,
        seller_owner_id=item.seller_owner_id,
        seller_name=owner_name(db, item.seller_owner_id),
        buyer_owner_id=item.buyer_owner_id,
        buyer_name=owner_name(db, item.buyer_owner_id),
        transaction_type=item.transaction_type,
        transaction_date=item.transaction_date,
        declared_value=item.declared_value,
        status=item.status,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_risk_level=risk.risk_level if risk else None,
        latest_risk_score=risk.risk_score if risk else None,
    )


def serialize_case(db: Session, item: CaseReview) -> CaseOut:
    transaction = db.query(Transaction).filter(Transaction.id == item.transaction_id).first()
    parcel = db.query(Parcel).filter(Parcel.id == item.parcel_id).first()
    assignee = db.query(User).filter(User.id == item.assigned_to).first() if item.assigned_to else None
    risk = latest_risk(db, item.transaction_id)
    return CaseOut(
        id=item.id,
        case_code=item.case_code,
        transaction_id=item.transaction_id,
        transaction_code=transaction.transaction_code if transaction else None,
        parcel_id=item.parcel_id,
        parcel_code=parcel.parcel_code if parcel else None,
        assigned_to=item.assigned_to,
        assigned_name=assignee.full_name if assignee else None,
        status=item.status,
        review_notes=item.review_notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        risk_level=risk.risk_level if risk else None,
    )


def serialize_audit(db: Session, item) -> AuditLogOut:
    user = db.query(User).filter(User.id == item.user_id).first() if item.user_id else None
    return AuditLogOut(
        id=item.id,
        user_id=item.user_id,
        user_name=user.full_name if user else None,
        action=item.action,
        entity=item.entity,
        entity_id=item.entity_id,
        audit_metadata=item.audit_metadata,
        details=item.details,
        created_at=item.created_at,
    )


def ensure_case(db: Session, transaction: Transaction, assigned_to: int | None = None) -> CaseReview:
    existing = db.query(CaseReview).filter(CaseReview.transaction_id == transaction.id).first()
    if existing:
        return existing
    count = db.query(CaseReview).count() + 1
    case = CaseReview(
        case_code=f"CASE-{count:04d}",
        transaction_id=transaction.id,
        parcel_id=transaction.parcel_id,
        assigned_to=assigned_to,
        status="OPEN",
    )
    db.add(case)
    db.flush()
    return case


def next_transaction_code(db: Session) -> str:
    count = db.query(Transaction).count() + 1
    return f"TX-{90000 + count}"
