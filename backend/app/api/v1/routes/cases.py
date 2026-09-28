from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.case_review import CASE_STATUSES, CaseReview
from app.models.ownership_history import OwnershipHistory
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.schemas.domain import CaseOut, CaseUpdate
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import serialize_case, serialize_history, serialize_transaction

router = APIRouter(prefix="/cases", tags=["Cases"])
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")
write_roles = require_roles("ADMIN", "OFFICER")


@router.get("", response_model=list[CaseOut])
def list_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(CaseReview)
    if status_filter:
        query = query.filter(CaseReview.status == status_filter)
    return [serialize_case(db, item) for item in query.order_by(CaseReview.updated_at.desc()).all()]


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
        "disclaimer": "Risk indicators are advisory. They are not legal proof of fraud or ownership.",
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
    previous = item.status
    if payload.status:
        item.status = payload.status
    if payload.review_notes is not None:
        item.review_notes = payload.review_notes
    if payload.assigned_to is not None:
        item.assigned_to = payload.assigned_to
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
