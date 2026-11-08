from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.transaction_status import TransactionStatus, UNRESOLVED_STATUSES
from app.db.session import get_db
from app.models.case_review import CaseReview, CaseStatusHistory
from app.models.evidence import Evidence, EvidenceReviewHistory
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction
from app.models.subdivision import Subdivision
from app.models.transaction import Transaction, TRANSACTION_STATUSES
from app.models.transaction_status_history import TransactionStatusHistory
from app.models.user import User
from app.models.verification_result import VerificationResultRecord
from app.schemas.domain import (
    OwnershipTransferRequest,
    TransactionCreate,
    TransactionOut,
    TransactionReviewDecision,
    TransactionReviewDetails,
)
from app.services.audit.service import record_audit
from app.services.auth.service import require_roles
from app.services.risk.service import RiskModelUnavailable, analyze_transaction
from app.services.serializers import ensure_case, next_transaction_code, serialize_history, serialize_transaction
from app.services.verification.service import verify_transaction

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Role definitions
write_roles = require_roles("ADMIN", "OFFICER")
registration_roles = require_roles("ADMIN", "OFFICER")
admin_roles = require_roles("ADMIN")
delete_roles = require_roles("ADMIN")
read_roles = require_roles("ADMIN", "OFFICER", "AUDITOR")


class TransactionStatusUpdate(BaseModel):
    status: str
    reason: str | None = None
    supporting_reference: str | None = None


class TransactionDeletionRequest(BaseModel):
    reason: str


VALID_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "PENDING_REVIEW": ["UNDER_REVIEW"],
    "PENDING": ["UNDER_REVIEW", "FLAGGED", "REJECTED"],  # Legacy compatibility
    "UNDER_REVIEW": ["VERIFIED", "APPROVED", "REJECTED", "FLAGGED", "AWAITING_EVIDENCE"],
    "AWAITING_EVIDENCE": ["UNDER_REVIEW"],
    "FLAGGED": ["UNDER_REVIEW", "REJECTED"],
    "VERIFIED": ["COMPLETED"],
    "APPROVED": ["COMPLETED"],  # Legacy compatibility
    "REJECTED": [],
    "COMPLETED": [],
}


def _execute_automated_checks(db: Session, transaction: Transaction) -> None:
    """Run automated verification rules and AI risk assessment."""
    try:
        verify_transaction(db, transaction)
    except Exception as exc:
        # Verification failure should not crash transaction, but be logged
        pass

    try:
        analyze_transaction(db, transaction)
    except (RiskModelUnavailable, Exception):
        # AI risk model failure should not block transaction creation
        pass

    try:
        ensure_case(db, transaction)
    except Exception:
        pass


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _current_user: User = Depends(read_roles),
):
    query = db.query(Transaction)
    if q:
        like = f"%{q}%"
        query = query.filter(Transaction.transaction_code.ilike(like))
    if status_filter:
        if status_filter in ["PENDING_REVIEW", "PENDING"]:
            query = query.filter(Transaction.status.in_(["PENDING_REVIEW", "PENDING"]))
        elif status_filter in ["VERIFIED", "APPROVED"]:
            query = query.filter(Transaction.status.in_(["VERIFIED", "APPROVED"]))
        else:
            query = query.filter(Transaction.status == status_filter)
    return [serialize_transaction(db, item) for item in query.order_by(Transaction.created_at.desc()).all()]


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(registration_roles),
):
    """Officer registers a new transaction. Sets status to PENDING_REVIEW and runs automated checks."""
    parcel = db.query(Parcel).filter(Parcel.id == payload.parcel_id).with_for_update().first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    if parcel.status.upper() != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active parcels can receive transactions")
    if parcel.has_pending_transaction or db.query(Transaction).filter(
        Transaction.parcel_id == parcel.id,
        Transaction.status.in_(UNRESOLVED_STATUSES),
    ).first():
        raise HTTPException(status_code=409, detail="Parcel already has an incompatible pending transaction")

    if payload.seller_owner_id is not None and not db.query(Owner).filter(
        Owner.id == payload.seller_owner_id
    ).first():
        raise HTTPException(status_code=404, detail="Seller not found")

    latest_ownership = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel.id)
        .order_by(
            OwnershipHistory.transfer_date.desc(),
            OwnershipHistory.id.desc(),
        )
        .first()
    )
    if not latest_ownership or not latest_ownership.new_owner_id:
        raise HTTPException(status_code=409, detail="Parcel has no valid current registered owner")
    seller_owner_id = latest_ownership.new_owner_id
    if payload.seller_owner_id is not None and payload.seller_owner_id != seller_owner_id:
        raise HTTPException(status_code=400, detail="Seller is determined by the parcel's current ownership record")

    buyer = db.query(Owner).filter(Owner.id == payload.buyer_owner_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer not found")
    if buyer.status.upper() != "ACTIVE":
        raise HTTPException(status_code=409, detail="Buyer must be an active owner")
    if seller_owner_id == buyer.id:
        raise HTTPException(
            status_code=400,
            detail="Seller and buyer cannot be the same person",
        )

    # Initial status is PENDING_REVIEW
    initial_status = TransactionStatus.PENDING_REVIEW.value

    item = Transaction(
        transaction_code=next_transaction_code(db),
        created_by=current_user.id,
        status=initial_status,
        parcel_id=parcel.id,
        seller_owner_id=seller_owner_id,
        buyer_owner_id=buyer.id,
        transaction_type=payload.transaction_type,
        transaction_date=payload.transaction_date,
        declared_value=payload.declared_value,
        supporting_reference=payload.supporting_reference,
    )
    db.add(item)
    db.flush()

    parcel.has_pending_transaction = True
    db.flush()

    # Record creation in status history
    db.add(
        TransactionStatusHistory(
            transaction_id=item.id,
            previous_status=None,
            new_status=initial_status,
            changed_by=current_user.id,
            reason="Transaction created and submitted for review",
        )
    )

    record_audit(
        db,
        action="TRANSACTION_CREATED",
        entity="Transaction",
        entity_id=item.transaction_code,
        user_id=current_user.id,
        metadata={"status": initial_status, "parcel_id": parcel.id, "created_by": current_user.username},
    )

    # Run automated checks
    _execute_automated_checks(db, item)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction could not be saved because a related record is invalid or already exists.",
        ) from exc

    db.refresh(item)
    return serialize_transaction(db, item)


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return serialize_transaction(db, item)


@router.get("/{transaction_id}/review-details", response_model=TransactionReviewDetails)
def get_transaction_review_details(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(read_roles),
):
    """Retrieve full details needed by the Admin Transaction Review Center and Auditor."""
    item = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found")

    parcel = db.query(Parcel).filter(Parcel.id == item.parcel_id).first()
    seller = db.query(Owner).filter(Owner.id == item.seller_owner_id).first() if item.seller_owner_id else None
    buyer = db.query(Owner).filter(Owner.id == item.buyer_owner_id).first() if item.buyer_owner_id else None

    # Latest registered owner
    latest_ownership = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == item.parcel_id)
        .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
        .first()
    )
    current_owner = (
        db.query(Owner).filter(Owner.id == latest_ownership.new_owner_id).first()
        if latest_ownership and latest_ownership.new_owner_id
        else None
    )

    # Ownership history
    history_records = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == item.parcel_id)
        .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
        .all()
    )

    # Evidence
    evidence_records = (
        db.query(Evidence)
        .filter(Evidence.transaction_id == item.id)
        .order_by(Evidence.created_at.desc())
        .all()
    )

    # Verification results
    verification_records = (
        db.query(VerificationResultRecord)
        .filter(VerificationResultRecord.transaction_id == item.id)
        .order_by(VerificationResultRecord.id)
        .all()
    )

    # AI Risk prediction
    risk_record = (
        db.query(RiskPrediction)
        .filter(RiskPrediction.transaction_id == item.id)
        .order_by(RiskPrediction.id.desc())
        .first()
    )

    # Status & review decisions history
    decisions = (
        db.query(TransactionStatusHistory)
        .filter(TransactionStatusHistory.transaction_id == item.id)
        .order_by(TransactionStatusHistory.created_at.desc())
        .all()
    )

    # Determine can_review permissions
    user_roles = {r.name for r in current_user.roles}
    is_admin = "ADMIN" in user_roles
    can_review = True
    cannot_review_reason = None

    if not is_admin:
        can_review = False
        cannot_review_reason = "Only system administrators have authorization to approve or review transactions."
    elif item.created_by == current_user.id:
        can_review = False
        cannot_review_reason = "Self-approval is forbidden: you registered this transaction. An independent administrator must review."
    elif item.status == "COMPLETED":
        can_review = False
        cannot_review_reason = "This transaction is COMPLETED and permanently finalized."

    return TransactionReviewDetails(
        transaction=serialize_transaction(db, item),
        parcel={
            "id": parcel.id,
            "parcel_code": parcel.parcel_code,
            "upi": parcel.upi,
            "location": parcel.location,
            "province": parcel.province,
            "district": parcel.district,
            "sector": parcel.sector,
            "cell": parcel.cell,
            "village": parcel.village,
            "area_ha": parcel.area_ha,
            "status": parcel.status,
            "registration_reference": parcel.registration_reference,
            "has_pending_transaction": parcel.has_pending_transaction,
        } if parcel else None,
        current_owner={
            "id": current_owner.id,
            "owner_code": current_owner.owner_code,
            "full_name": current_owner.full_name,
            "identification_number": current_owner.identification_number,
            "phone": current_owner.phone,
            "email": current_owner.email,
            "status": current_owner.status,
        } if current_owner else None,
        seller={
            "id": seller.id,
            "owner_code": seller.owner_code,
            "full_name": seller.full_name,
            "identification_number": seller.identification_number,
            "status": seller.status,
        } if seller else None,
        buyer={
            "id": buyer.id,
            "owner_code": buyer.owner_code,
            "full_name": buyer.full_name,
            "identification_number": buyer.identification_number,
            "status": buyer.status,
        } if buyer else None,
        evidence=[
            {
                "id": ev.id,
                "document_type": ev.document_type,
                "original_filename": ev.original_filename,
                "mime_type": ev.mime_type,
                "status": ev.status,
                "payment_reference": ev.payment_reference,
                "stated_payment_amount": ev.stated_payment_amount,
                "notes": ev.notes,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in evidence_records
        ],
        ownership_history=[
            serialize_history(db, h).model_dump()
            for h in history_records
        ],
        ai_risk={
            "risk_score": risk_record.risk_score,
            "risk_level": risk_record.risk_level,
            "explanation": risk_record.explanation,
            "indicators": risk_record.indicators,
            "model_version": risk_record.model_version,
            "disclaimer": "AI risk assessment provides advisory recommendations and decision support only; it does not make legally authoritative ownership decisions.",
        } if risk_record else None,
        verification_results=[
            {
                "rule_name": v.rule_name,
                "status": v.result,
                "severity": v.severity,
                "explanation": v.explanation,
            }
            for v in verification_records
        ],
        review_decisions=[
            {
                "id": d.id,
                "previous_status": d.previous_status,
                "new_status": d.new_status,
                "changed_by": d.changed_by,
                "reason": d.reason,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
        can_review=can_review,
        cannot_review_reason=cannot_review_reason,
    )


@router.post("/{transaction_id}/review-decision", response_model=TransactionOut)
def submit_review_decision(
    transaction_id: int,
    payload: TransactionReviewDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_roles),
):
    """Admin review decision on a transaction."""
    explanation = (payload.explanation or "").strip()
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An explanation is required for all review decisions.",
        )

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).with_for_update().first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    current_status = transaction.status
    if current_status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed transactions are permanently finalized and cannot be modified.",
        )

    # Map actions to target statuses
    action_status_map = {
        "START_REVIEW": "UNDER_REVIEW",
        "VERIFY": "VERIFIED",
        "APPROVE": "VERIFIED",
        "REJECT": "REJECTED",
        "FLAG": "FLAGGED",
        "REQUEST_EVIDENCE": "AWAITING_EVIDENCE",
        "RESUME_REVIEW": "UNDER_REVIEW",
        "RESOLVE_FLAG": "UNDER_REVIEW",
    }

    target_status = action_status_map.get(payload.action.upper())
    if not target_status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{payload.action}'. Supported actions: {', '.join(action_status_map.keys())}",
        )

    # Self-approval protection
    if transaction.created_by == current_user.id and target_status in ["VERIFIED", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval is forbidden. A different administrator must review and approve this transaction.",
        )

    # Validate transition
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition transaction from {current_status} to {target_status}. Allowed: {', '.join(allowed)}",
        )

    # Investigation requirement for FLAGGED transactions
    if current_status == "FLAGGED" and payload.action.upper() == "RESOLVE_FLAG":
        findings = (payload.investigation_findings or "").strip()
        if not findings and len(explanation) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resolving a flagged transaction requires authorized investigation findings and explanation.",
            )

    parcel = db.query(Parcel).filter(Parcel.id == transaction.parcel_id).first()

    # If rejected, clear pending flag on parcel
    if target_status == "REJECTED" and parcel:
        parcel.has_pending_transaction = False

    transaction.status = target_status
    db.flush()

    status_history = TransactionStatusHistory(
        transaction_id=transaction.id,
        previous_status=current_status,
        new_status=target_status,
        changed_by=current_user.id,
        reason=f"[{payload.action.upper()}] {explanation}" + (f" | Findings: {payload.investigation_findings}" if payload.investigation_findings else ""),
    )
    db.add(status_history)

    record_audit(
        db,
        action=f"TRANSACTION_{payload.action.upper()}",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={
            "from": current_status,
            "to": target_status,
            "action": payload.action.upper(),
            "explanation": explanation,
            "investigation_findings": payload.investigation_findings,
            "evidence_notes": payload.evidence_notes,
        },
    )

    # Sync with CaseReview if exists
    case = db.query(CaseReview).filter(CaseReview.transaction_id == transaction.id).first()
    if case:
        if target_status == "UNDER_REVIEW":
            case.status = "UNDER_REVIEW"
        elif target_status in ["VERIFIED", "APPROVED"]:
            case.status = "RESOLVED"
        elif target_status == "REJECTED":
            case.status = "CLOSED"
        elif target_status == "AWAITING_EVIDENCE":
            case.status = "NEEDS_INFORMATION"
        case.review_notes = explanation
        db.flush()

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record review decision. Changes were rolled back.",
        ) from exc

    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.post("/{transaction_id}/confirm-transfer", response_model=TransactionOut)
def confirm_ownership_transfer(
    transaction_id: int,
    payload: OwnershipTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_roles),
):
    """
    Confirms official land ownership transfer.
    Requirements:
    - Must be ADMIN.
    - Transaction must be VERIFIED or APPROVED.
    - User who registered transaction cannot self-confirm.
    - For partial sales, requires existing approved subdivision.
    - Updates ownership_history and marks COMPLETED.
    """
    reference = payload.supporting_reference.strip()
    if not reference:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An official transfer reference (e.g., deed number or registrar confirmation reference) is required.",
        )

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).with_for_update().first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ownership transfer has already been completed for this transaction.",
        )

    if transaction.status not in ["VERIFIED", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete transfer: transaction must first be VERIFIED or APPROVED by an administrator. Current status is {transaction.status}.",
        )

    # Prevent self-approval / self-transfer
    if transaction.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-confirmation is forbidden. An independent administrator must confirm the ownership transfer.",
        )

    if not transaction.seller_owner_id or not transaction.buyer_owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transfer requires both a recorded seller and an active buyer.",
        )

    buyer = db.query(Owner).filter(Owner.id == transaction.buyer_owner_id).first()
    if not buyer or buyer.status.upper() != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transfer buyer must be an active owner.")

    parcel = db.query(Parcel).filter(Parcel.id == transaction.parcel_id).with_for_update().first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Partial parcel sales handling
    target_parcel_id = parcel.id
    if transaction.transaction_type in ["PARTIAL_SALE", "SUBDIVISION"]:
        subdivision = (
            db.query(Subdivision)
            .filter(
                Subdivision.parent_parcel_id == parcel.id,
                Subdivision.status.in_(["APPROVED", "COMPLETED"]),
            )
            .first()
        )
        if not subdivision or not subdivision.new_parcel_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Partial parcel sales cannot transfer the entire parent parcel. An approved subdivision with an assigned child parcel is required. Please complete the subdivision workflow first.",
            )
        target_parcel_id = subdivision.new_parcel_id

    # Verify latest owner of target parcel
    latest_ownership = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel.id)
        .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
        .first()
    )
    if not latest_ownership or latest_ownership.new_owner_id != transaction.seller_owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot complete transfer: seller does not match the latest registered owner of the parcel.",
        )

    previous_status = transaction.status

    try:
        # 1. Append to ownership_history
        new_ownership = OwnershipHistory(
            parcel_id=target_parcel_id,
            previous_owner_id=transaction.seller_owner_id,
            new_owner_id=transaction.buyer_owner_id,
            transfer_date=datetime.utcnow(),
            reason_type=transaction.transaction_type,
            supporting_reference=reference,
        )
        db.add(new_ownership)

        # 2. Update transaction
        transaction.status = "COMPLETED"
        transaction.supporting_reference = reference
        db.flush()

        # 3. Update parcel flags
        parcel.has_pending_transaction = False
        db.flush()

        # 4. Record status history
        db.add(
            TransactionStatusHistory(
                transaction_id=transaction.id,
                previous_status=previous_status,
                new_status="COMPLETED",
                changed_by=current_user.id,
                reason=f"Official ownership transfer confirmed. Reference: {reference}. Notes: {payload.notes or 'None'}",
            )
        )

        # 5. Audit logs
        record_audit(
            db,
            action="OWNERSHIP_TRANSFERRED",
            entity="Parcel",
            entity_id=parcel.parcel_code or f"PARCEL-{parcel.id}",
            user_id=current_user.id,
            metadata={
                "transaction_code": transaction.transaction_code,
                "parcel_id": target_parcel_id,
                "previous_owner_id": transaction.seller_owner_id,
                "new_owner_id": transaction.buyer_owner_id,
                "supporting_reference": reference,
                "confirmed_by": current_user.username,
            },
        )

        record_audit(
            db,
            action="TRANSACTION_STATUS_CHANGED",
            entity="Transaction",
            entity_id=transaction.transaction_code,
            user_id=current_user.id,
            metadata={
                "from": previous_status,
                "to": "COMPLETED",
                "reason": f"Official transfer confirmed. Reference: {reference}",
            },
        )

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ownership transfer transaction failed and was rolled back.",
        ) from exc

    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.put("/{transaction_id}/status", response_model=TransactionOut)
def update_transaction_status(
    transaction_id: int,
    payload: TransactionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(write_roles),
):
    """
    Update transaction status with strict RBAC:
    - Officers cannot approve, verify, or complete transactions.
    - Admins cannot self-approve.
    - Completed transactions are immutable.
    - Reasons are mandatory.
    """
    if payload.status not in TRANSACTION_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(TRANSACTION_STATUSES)}")

    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An explanation is required for all status transitions.",
        )

    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).with_for_update().first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    current_status = transaction.status
    if current_status == payload.status:
        raise HTTPException(status_code=400, detail="Transaction is already in this status")

    if current_status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed transactions are permanently finalized and cannot be modified.",
        )

    user_roles = {r.name for r in current_user.roles}
    is_admin = "ADMIN" in user_roles

    # RBAC: Only Admin can approve, verify, flag, reject, or complete
    if payload.status in ["VERIFIED", "APPROVED", "COMPLETED", "REJECTED", "FLAGGED"] and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can approve, reject, flag, or complete transactions.",
        )

    # Self-approval check
    if transaction.created_by == current_user.id and payload.status in ["VERIFIED", "APPROVED", "COMPLETED"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval is forbidden. A different administrator must review and approve this transaction.",
        )

    allowed_transitions = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if payload.status not in allowed_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current_status} to {payload.status}. Allowed: {', '.join(allowed_transitions)}",
        )

    parcel = db.query(Parcel).filter(Parcel.id == transaction.parcel_id).first()
    ownership_entry = None

    if payload.status == "COMPLETED":
        if current_status not in ["APPROVED", "VERIFIED"]:
            raise HTTPException(
                status_code=400,
                detail="Only approved/verified transactions can complete ownership transfers.",
            )

        if not transaction.seller_owner_id or not transaction.buyer_owner_id:
            raise HTTPException(
                status_code=409,
                detail="Transfer requires both a seller and a buyer.",
            )

        buyer = db.query(Owner).filter(Owner.id == transaction.buyer_owner_id).first()
        if not buyer:
            raise HTTPException(status_code=409, detail="Transfer buyer was not found.")

        # Partial parcel sale check
        target_parcel_id = transaction.parcel_id
        if transaction.transaction_type in ["PARTIAL_SALE", "SUBDIVISION"]:
            subdivision = (
                db.query(Subdivision)
                .filter(
                    Subdivision.parent_parcel_id == transaction.parcel_id,
                    Subdivision.status.in_(["APPROVED", "COMPLETED"]),
                )
                .first()
            )
            if not subdivision or not subdivision.new_parcel_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Partial parcel sales cannot transfer the entire parent parcel. An approved subdivision with an assigned child parcel is required.",
                )
            target_parcel_id = subdivision.new_parcel_id

        latest_ownership = (
            db.query(OwnershipHistory)
            .filter(OwnershipHistory.parcel_id == transaction.parcel_id)
            .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
            .first()
        )

        if latest_ownership is None or latest_ownership.new_owner_id is None:
            raise HTTPException(
                status_code=409,
                detail="Cannot complete transfer: current recorded ownership is not established.",
            )

        if latest_ownership.new_owner_id != transaction.seller_owner_id:
            raise HTTPException(
                status_code=409,
                detail="Cannot complete transfer: seller does not match the latest recorded owner.",
            )

        transfer_ref = payload.supporting_reference or transaction.supporting_reference or transaction.transaction_code
        ownership_entry = OwnershipHistory(
            parcel_id=target_parcel_id,
            previous_owner_id=transaction.seller_owner_id,
            new_owner_id=transaction.buyer_owner_id,
            transfer_date=datetime.utcnow(),
            reason_type=transaction.transaction_type,
            supporting_reference=transfer_ref,
        )

    try:
        transaction.status = payload.status
        db.flush()

        if ownership_entry is not None:
            db.add(ownership_entry)
            db.flush()

        status_history = TransactionStatusHistory(
            transaction_id=transaction.id,
            previous_status=current_status,
            new_status=payload.status,
            changed_by=current_user.id,
            reason=reason,
        )
        db.add(status_history)

        # Update parcel pending flag
        if parcel:
            has_pending = (
                db.query(Transaction)
                .filter(
                    Transaction.parcel_id == transaction.parcel_id,
                    Transaction.status.in_(UNRESOLVED_STATUSES),
                )
                .first()
            ) is not None
            parcel.has_pending_transaction = has_pending
            db.flush()

        record_audit(
            db,
            action="TRANSACTION_STATUS_CHANGED",
            entity="Transaction",
            entity_id=transaction.transaction_code,
            user_id=current_user.id,
            metadata={"from": current_status, "to": payload.status, "reason": reason},
        )

        if payload.status == "COMPLETED" and parcel:
            record_audit(
                db,
                action="OWNERSHIP_TRANSFERRED",
                entity="Parcel",
                entity_id=parcel.parcel_code or f"PARCEL-{parcel.id}",
                user_id=current_user.id,
                metadata={
                    "transaction_code": transaction.transaction_code,
                    "previous_owner_id": transaction.seller_owner_id,
                    "new_owner_id": transaction.buyer_owner_id,
                    "confirmed_by": current_user.username,
                },
            )

        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction status update failed and was rolled back.",
        ) from exc

    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.get("/{transaction_id}/verification")
def get_stored_verification(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Transaction).filter(Transaction.id == transaction_id).first():
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(VerificationResultRecord)
        .filter(VerificationResultRecord.transaction_id == transaction_id)
        .order_by(VerificationResultRecord.id)
        .all()
    )
    return [
        {
            "rule_name": row.rule_name,
            "status": row.result,
            "severity": row.severity,
            "explanation": row.explanation,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/{transaction_id}/status-history")
def get_transaction_status_history(transaction_id: int, db: Session = Depends(get_db), _current_user: User = Depends(read_roles)):
    if not db.query(Transaction).filter(Transaction.id == transaction_id).first():
        raise HTTPException(status_code=404, detail="Transaction not found")
    rows = (
        db.query(TransactionStatusHistory)
        .filter(TransactionStatusHistory.transaction_id == transaction_id)
        .order_by(TransactionStatusHistory.created_at.desc())
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


@router.post("/{transaction_id}/archive", response_model=TransactionOut)
def archive_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(delete_roles),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.is_archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction is already archived")

    transaction.is_archived = True
    transaction.archived_at = datetime.utcnow()
    transaction.archived_by = current_user.id
    record_audit(
        db,
        action="TRANSACTION_ARCHIVED",
        entity="Transaction",
        entity_id=transaction.transaction_code,
        user_id=current_user.id,
        metadata={"reason": "Transaction archived by authorized administrator"},
    )
    db.commit()
    db.refresh(transaction)
    return serialize_transaction(db, transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    payload: TransactionDeletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(delete_roles),
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A deletion reason is required.",
        )
    if transaction.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed transactions cannot be permanently deleted. Archive this transaction instead.",
        )

    parcel_id = transaction.parcel_id
    transaction_code = transaction.transaction_code

    try:
        evidence_ids = [
            evidence_id
            for evidence_id, in db.query(Evidence.id)
            .filter(Evidence.transaction_id == transaction_id)
            .all()
        ]
        if evidence_ids:
            db.query(EvidenceReviewHistory).filter(
                EvidenceReviewHistory.evidence_id.in_(evidence_ids)
            ).delete(synchronize_session=False)
        db.query(Evidence).filter(
            Evidence.transaction_id == transaction_id
        ).delete(synchronize_session=False)

        case_ids = [
            case_id
            for case_id, in db.query(CaseReview.id)
            .filter(CaseReview.transaction_id == transaction_id)
            .all()
        ]
        if case_ids:
            db.query(CaseStatusHistory).filter(
                CaseStatusHistory.case_id.in_(case_ids)
            ).delete(synchronize_session=False)
        db.query(CaseReview).filter(
            CaseReview.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(RiskPrediction).filter(
            RiskPrediction.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(TransactionStatusHistory).filter(
            TransactionStatusHistory.transaction_id == transaction_id
        ).delete(synchronize_session=False)
        db.query(VerificationResultRecord).filter(
            VerificationResultRecord.transaction_id == transaction_id
        ).delete(synchronize_session=False)

        db.delete(transaction)
        db.flush()

        parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
        if parcel:
            parcel.has_pending_transaction = db.query(Transaction).filter(
                Transaction.parcel_id == parcel_id,
                Transaction.status.in_(UNRESOLVED_STATUSES),
            ).first() is not None

        record_audit(
            db,
            action="TRANSACTION_DELETED",
            entity="Transaction",
            entity_id=transaction_code,
            user_id=current_user.id,
            metadata={
                "reason": reason,
                "deletion_policy": "ADMIN_CONFIRMED_NON_COMPLETED_TRANSACTION",
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction cannot be deleted because related records are still protected.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction deletion failed and all changes were rolled back.",
        ) from exc
