from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.case_review import CaseReview, CaseStatusHistory, CASE_PRIORITIES, CASE_STATUSES
from app.models.ownership_history import OwnershipHistory
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.schemas.domain import CaseCreate, CaseOut, CaseUpdate
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import ensure_case, serialize_case, serialize_history, serialize_transaction

router = APIRouter(prefix="/cases", tags=["Cases"])
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")
write_roles = require_roles("ADMIN", "OFFICER")


@router.get("", response_model=list[CaseOut])
def list_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    priority_filter: str | None = Query(default=None, alias="priority"),
    assigned_to: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(CaseReview)
    if status_filter:
        query = query.filter(CaseReview.status == status_filter)
    if priority_filter:
        query = query.filter(CaseReview.priority == priority_filter)
    if assigned_to is not None:
        query = query.filter(CaseReview.assigned_to == assigned_to)
    return [serialize_case(db, item) for item in query.order_by(CaseReview.updated_at.desc()).all()]


@router.post("", response_model=CaseOut, status_code=201)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    transaction = db.query(Transaction).filter(Transaction.id == payload.transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Check if case already exists for this transaction
    existing = db.query(CaseReview).filter(CaseReview.transaction_id == payload.transaction_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Case already exists for this transaction")

    if payload.priority not in CASE_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Priority must be one of: {', '.join(CASE_PRIORITIES)}")

    count = db.query(CaseReview).count() + 1
    case = CaseReview(
        case_code=f"CASE-{count:04d}",
        transaction_id=payload.transaction_id,
        parcel_id=transaction.parcel_id,
        assigned_to=payload.assigned_to,
        status="OPEN",
        priority=payload.priority,
        review_notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(case)
    db.flush()

    # Record initial status in history
    status_history = CaseStatusHistory(
        case_id=case.id,
        previous_status=None,
        new_status="OPEN",
        changed_by=current_user.id,
        reason="Case created",
    )
    db.add(status_history)

    record_audit(db, action="CASE_CREATED", entity="Case", entity_id=case.case_code, user_id=current_user.id)
    db.commit()
    db.refresh(case)
    return serialize_case(db, case)


@router.get("/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    item = db.query(CaseReview).filter(CaseReview.id == case_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Case not found")
    transaction = db.query(Transaction).filter(Transaction.id == item.transaction_id).first()
    history = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == item.parcel_id)
        .order_by(OwnershipHistory.transfer_date.asc())
        .all()
    )
    verification = (
        db.query(VerificationResultRecord)
        .filter(VerificationResultRecord.transaction_id == item.transaction_id)
        .all()
    )
    risk = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.transaction_id == item.transaction_id)
        .order_by(RiskPrediction.created_at.desc())
        .first()
    )
    status_history = (
        db.query(CaseStatusHistory)
        .filter(CaseStatusHistory.case_id == item.id)
        .order_by(CaseStatusHistory.created_at.desc())
        .all()
    )
    return {
        "case": serialize_case(db, item),
        "transaction": serialize_transaction(db, transaction) if transaction else None,
        "ownership_history": [serialize_history(db, row) for row in history],
        "verification_results": [
            {
                "rule_name": row.rule_name,
                "status": row.result,
                "severity": row.severity,
                "explanation": row.explanation,
            }
            for row in verification
        ],
        "risk": {
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level,
            "model_version": risk.model_version,
            "reasons": risk.indicators or [],
        }
        if risk
        else None,
        "status_history": [
            {
                "previous_status": row.previous_status,
                "new_status": row.new_status,
                "changed_by": row.changed_by,
                "reason": row.reason,
                "created_at": row.created_at,
            }
            for row in status_history
        ],
        "disclaimer": "Risk indicators are advisory. Final decisions remain with authorized human officers.",
    }


@router.put("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    item = db.query(CaseReview).filter(CaseReview.id == case_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Case not found")
    if payload.status and payload.status not in CASE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid case status")
    if payload.priority and payload.priority not in CASE_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid case priority")

    previous = item.status
    if payload.status and payload.status != previous:
        item.status = payload.status
        # Record status change in history
        status_history = CaseStatusHistory(
            case_id=item.id,
            previous_status=previous,
            new_status=payload.status,
            changed_by=current_user.id,
            reason="Status updated via case review",
        )
        db.add(status_history)
    if payload.review_notes is not None:
        item.review_notes = payload.review_notes
    if payload.resolution_notes is not None:
        item.resolution_notes = payload.resolution_notes
    if payload.assigned_to is not None:
        item.assigned_to = payload.assigned_to
    if payload.priority is not None:
        item.priority = payload.priority
    if payload.due_date is not None:
        item.due_date = payload.due_date

    record_audit(
        db,
        action="CASE_REVIEWED",
        entity="Case",
        entity_id=item.case_code,
        user_id=current_user.id,
        metadata={"from": previous, "to": item.status},
    )
    db.commit()
    db.refresh(item)
    return serialize_case(db, item)


@router.get("/{case_id}/status-history")
def get_case_status_history(case_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(CaseReview).filter(CaseReview.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
    rows = (
        db.query(CaseStatusHistory)
        .filter(CaseStatusHistory.case_id == case_id)
        .order_by(CaseStatusHistory.created_at.desc())
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
