"""Public API endpoints for citizen UPI checking; no authentication required."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parcel import Parcel
from app.models.transaction import Transaction
from app.schemas.domain import PublicParcelOut

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/parcels/{upi}", response_model=PublicParcelOut)
def public_parcel_check(upi: str, db: Session = Depends(get_db)):
    """Public endpoint for citizens to check parcel status by UPI.

    Returns only safe, non-sensitive information:
    - UPI and parcel code
    - Location and district
    - Parcel status
    - Whether a pending/conflicting transaction exists
    - General verification warning

    Does NOT expose:
    - Owner personal information
    - Seller/buyer details
    - Contact information
    - Internal audit data
    - Investigation notes
    """
    parcel = db.query(Parcel).filter(Parcel.upi == upi).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    upi_normalized = (parcel.upi or "").strip().upper()
    registration_reference = (parcel.registration_reference or "").strip().upper()

    is_synthetic = (
        upi_normalized.startswith("DEMO-UPI-")
        or registration_reference.startswith("DEMO-PARCEL-")
    )

    record_classification = (
        "DEMO_SYNTHETIC" if is_synthetic else "UNVERIFIED_LOCAL_RECORD"
    )
    # Check for pending or conflicting transactions
    pending_tx = (
        db.query(Transaction)
        .filter(
            Transaction.parcel_id == parcel.id,
            Transaction.status.in_(["PENDING", "UNDER_REVIEW", "FLAGGED"]),
        )
        .first()
    )

    has_pending = pending_tx is not None

    warning = None
    if has_pending:
        warning = (
            "WARNING: This parcel has a pending or under-review transaction. "
            "Please exercise caution and verify with the official land authority "
            "before proceeding with any transaction."
        )
    elif parcel.status == "DISPUTED":
        warning = (
            "WARNING: This parcel is currently marked as disputed. "
            "Please consult the official land authority for clarification."
        )
    elif parcel.status == "UNDER_REVIEW":
        warning = (
            "NOTICE: This parcel is currently under review. "
            "Please verify the current status with the official land authority."
        )

    return PublicParcelOut(
        upi=parcel.upi,
        parcel_code=parcel.parcel_code,
        location=parcel.location,
        district=parcel.district,
        status=parcel.status,
        has_pending_transaction=has_pending,
        warning_message=warning,
        record_classification=record_classification,
        official_verification="NOT_INDEPENDENTLY_VERIFIED",
    )
