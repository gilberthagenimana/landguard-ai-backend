from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.case_review import CaseReview
from app.models.owner import Owner
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth.service import require_roles
from app.services.serializers import latest_risk

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _latest_risk_counts(db: Session) -> dict[str, int]:
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    transactions = db.query(Transaction).all()
    for item in transactions:
        risk = latest_risk(db, item.id)
        if risk and risk.risk_level in counts:
            counts[risk.risk_level] += 1
    return counts


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "OFFICER", "AUDITOR")),
):
    activity = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
    open_cases = (
        db.query(CaseReview)
        .filter(CaseReview.status.in_(("OPEN", "UNDER_REVIEW", "NEEDS_INFORMATION")))
        .order_by(CaseReview.updated_at.desc())
        .limit(8)
        .all()
    )
    risk_counts = _latest_risk_counts(db)
    return {
        "total_parcels": db.query(func.count(Parcel.id)).scalar() or 0,
        "total_owners": db.query(func.count(Owner.id)).scalar() or 0,
        "total_transactions": db.query(func.count(Transaction.id)).scalar() or 0,
        "transactions_under_review": db.query(func.count(CaseReview.id))
        .filter(CaseReview.status.in_(("OPEN", "UNDER_REVIEW", "NEEDS_INFORMATION")))
        .scalar()
        or 0,
        "low_risk_transactions": risk_counts["LOW"],
        "medium_risk_transactions": risk_counts["MEDIUM"],
        "high_risk_transactions": risk_counts["HIGH"],
        "recent_verification_activity": [
            {
                "action": item.action,
                "entity": item.entity,
                "entity_id": item.entity_id,
                "created_at": item.created_at.isoformat(),
            }
            for item in activity
        ],
        "recent_alerts": [
            {
                "id": item.case_code,
                "title": item.status.replace("_", " ").title(),
                "meta": item.updated_at.isoformat(),
                "risk": (latest_risk(db, item.transaction_id).risk_level if latest_risk(db, item.transaction_id) else "MEDIUM"),
            }
            for item in open_cases
        ],
        "viewer_role": next((role.name for role in current_user.roles), None),
    }
