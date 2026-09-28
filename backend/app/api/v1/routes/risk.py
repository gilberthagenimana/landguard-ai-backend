from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.risk import RiskAnalysisResponse
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.risk.service import RiskModelUnavailable, analyze_transaction
from app.services.serializers import ensure_case

router = APIRouter(prefix="/risk-analysis", tags=["Risk Analysis"])


class RiskRequest(BaseModel):
    transaction_id: int


@router.post("", response_model=RiskAnalysisResponse)
@router.post("/transactions/{transaction_id}", response_model=RiskAnalysisResponse)
def analyze_transaction_route(
    transaction_id: int | None = None,
    payload: RiskRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "OFFICER")),
):
    resolved_id = transaction_id or (payload.transaction_id if payload else None)
    if resolved_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="transaction_id is required")
    transaction = db.query(Transaction).filter(Transaction.id == resolved_id).first()
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    try:
        result = analyze_transaction(db, transaction)
    except RiskModelUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Risk model is not trained. Run the ML training command first.",
        ) from exc
    if result.risk_level in {"MEDIUM", "HIGH"}:
        ensure_case(db, transaction, assigned_to=current_user.id)
        if transaction.status == "PENDING":
            transaction.status = "UNDER_REVIEW"
    record_audit(
        db,
        action="AI_RISK_ANALYSIS",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={"risk_level": result.risk_level, "risk_score": result.risk_score},
    )
    db.commit()
    return result


@router.get("/transactions/{transaction_id}", response_model=list[RiskAnalysisResponse])
def list_predictions(
    transaction_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_roles("ADMIN", "OFFICER", "AUDITOR")),
):
    rows = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.transaction_id == transaction_id)
        .order_by(RiskPrediction.created_at.desc())
        .all()
    )
    return [
        RiskAnalysisResponse(
            transaction_id=row.transaction_id,
            risk_score=row.risk_score,
            risk_level=row.risk_level,  # type: ignore[arg-type]
            model_version=row.model_version,
            reasons=list(row.indicators or []),
            analyzed_at=row.created_at,
        )
        for row in rows
    ]
