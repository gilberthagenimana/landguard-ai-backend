from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.verification import VerificationResponse
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.serializers import ensure_case
from app.services.verification.service import verify_transaction

router = APIRouter(prefix="/verification", tags=["Verification"])


class VerificationRequest(BaseModel):
    transaction_id: int


@router.post("", response_model=VerificationResponse)
@router.post("/transactions/{transaction_id}", response_model=VerificationResponse)
def verify_transaction_route(
    transaction_id: int | None = None,
    payload: VerificationRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "OFFICER")),
):
    resolved_id = transaction_id or (payload.transaction_id if payload else None)
    if resolved_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="transaction_id is required")
    transaction = db.query(Transaction).filter(Transaction.id == resolved_id).first()
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    results = verify_transaction(db, transaction)
    overall_status = "PASS" if all(result.status == "PASS" for result in results) else "REVIEW_REQUIRED"
    if overall_status == "REVIEW_REQUIRED":
        ensure_case(db, transaction, assigned_to=current_user.id)
        if transaction.status == "PENDING":
            transaction.status = "UNDER_REVIEW"
    record_audit(
        db,
        action="TRANSACTION_VERIFICATION",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={"overall_status": overall_status},
    )
    db.commit()
    return VerificationResponse(
        transaction_id=transaction.id,
        overall_status=overall_status,
        verified_at=datetime.now(timezone.utc),
        results=results,
    )
