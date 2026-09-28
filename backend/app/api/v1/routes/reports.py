from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.case_review import CaseReview
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.services.auth.service import require_roles
from app.services.serializers import serialize_audit, serialize_case, serialize_history, serialize_transaction

router = APIRouter(prefix="/reports", tags=["Reports"])
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


@router.get("/verification")
def verification_report(db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    rows = db.query(VerificationResultRecord).order_by(VerificationResultRecord.created_at.desc()).limit(200).all()
    return {
        "title": "Transaction verification report",
        "disclaimer": "Synthetic/demo records. Not official land data.",
        "items": [
            {
                "date": row.created_at,
                "transaction_id": row.transaction_id,
                "rule_name": row.rule_name,
                "result": row.result,
                "severity": row.severity,
                "explanation": row.explanation,
            }
            for row in rows
        ],
    }


@router.get("/risk")
def risk_report(db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    rows = db.query(RiskPrediction).order_by(RiskPrediction.created_at.desc()).limit(200).all()
    return {
        "title": "Risk analysis report",
        "disclaimer": "AI results are risk indicators only and are not legal proof of fraud.",
        "items": [
            {
                "date": row.created_at,
                "transaction_id": row.transaction_id,
                "risk_score": row.risk_score,
                "risk_level": row.risk_level,
                "model_version": row.model_version,
                "reasons": row.indicators,
            }
            for row in rows
        ],
    }


@router.get("/cases")
def cases_report(db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    rows = db.query(CaseReview).order_by(CaseReview.updated_at.desc()).all()
    return {
        "title": "Suspicious cases report",
        "disclaimer": "Case status is set by an authorized human reviewer.",
        "items": [serialize_case(db, item) for item in rows],
    }


@router.get("/audit")
def audit_report(db: Session = Depends(get_db), current_user: User = Depends(require_roles("ADMIN", "AUDITOR"))):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return {
        "title": "Audit activity report",
        "items": [serialize_audit(db, item) for item in rows],
    }


@router.get("/parcels/{parcel_id}/history")
def parcel_history_report(parcel_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    history = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel_id)
        .order_by(OwnershipHistory.transfer_date.asc())
        .all()
    )
    transactions = db.query(Transaction).filter(Transaction.parcel_id == parcel_id).all()
    return {
        "title": "Parcel transaction history report",
        "parcel_code": parcel.parcel_code,
        "disclaimer": "Synthetic/demo records. Not official land data.",
        "ownership_history": [serialize_history(db, item) for item in history],
        "transactions": [serialize_transaction(db, item) for item in transactions],
    }
