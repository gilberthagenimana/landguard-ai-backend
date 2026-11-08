"""Public API endpoints for citizen UPI checking; no authentication required."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parcel import Parcel
from app.schemas.domain import PublicParcelOut
from app.services.transactions.service import get_latest_transaction, get_unresolved_transaction

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

    # Availability is derived from the parcel's real unresolved transactions.
    unresolved = get_unresolved_transaction(db, parcel.id)
    latest = get_latest_transaction(db, parcel.id)
    has_pending = unresolved is not None

    transaction_id = unresolved.id if unresolved else (latest.id if latest else None)
    transaction_code = unresolved.transaction_code if unresolved else (latest.transaction_code if latest else None)
    transaction_status = unresolved.status if unresolved else (latest.status if latest else None)

    availability = (
        "UNAVAILABLE"
        if unresolved
        else (
            "COMPLETED"
            if (latest is not None and latest.status == "COMPLETED")
            else ("RESTRICTED" if parcel.status.upper() == "DISPUTED" else "AVAILABLE")
        )
    )

    warning = None
    if unresolved is not None:
        if unresolved.status in ("PENDING_REVIEW", "PENDING"):
            warning = (
                "PENDING TRANSACTION — NOT AVAILABLE FOR ANOTHER SALE. "
                "The ownership transfer is pending and the parcel is unavailable."
            )
        elif unresolved.status == "UNDER_REVIEW":
            warning = (
                "UNDER REVIEW — OWNERSHIP TRANSFER NOT YET CONFIRMED. "
                "The parcel is not available for another sale."
            )
        elif unresolved.status == "AWAITING_EVIDENCE":
            warning = (
                "AWAITING EVIDENCE — OWNERSHIP TRANSFER NOT YET CONFIRMED. "
                "The parcel is not available for another sale."
            )
        elif unresolved.status == "FLAGGED":
            warning = (
                "FLAGGED — FURTHER INVESTIGATION REQUIRED. "
                "The parcel remains restricted pending investigation."
            )
        elif unresolved.status == "VERIFIED":
            warning = (
                "VERIFIED — OWNERSHIP TRANSFER PENDING CONFIRMATION. "
                "The parcel remains unavailable until the transfer is completed."
            )
        elif unresolved.status == "APPROVED":
            warning = (
                "APPROVED — OWNERSHIP TRANSFER PENDING FINAL CONFIRMATION. "
                "The parcel remains unavailable until completion is confirmed."
            )
    elif parcel.status.upper() == "DISPUTED":
        warning = (
            "WARNING: This parcel is currently marked as disputed. "
            "Please consult the official land authority for clarification."
        )

    return PublicParcelOut(
        upi=parcel.upi,
        parcel_code=parcel.parcel_code,
        location=parcel.location,
        district=parcel.district,
        status=parcel.status,
        availability=availability,
        has_pending_transaction=has_pending,
        transaction_id=transaction_id,
        transaction_code=transaction_code,
        transaction_status=transaction_status,
        warning_message=warning,
        record_classification=record_classification,
        official_verification="NOT_INDEPENDENTLY_VERIFIED",
    )
