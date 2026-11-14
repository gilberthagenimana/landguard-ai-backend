"""Public API endpoints for citizen parcel checking; no authentication required."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parcel import Parcel
from app.schemas.domain import PublicParcelOut
from app.services.serializers import latest_owner, owner_name
from app.services.transactions.service import get_latest_transaction, get_unresolved_transaction

router = APIRouter(prefix="/public", tags=["Public"])


def _public_parcel_response(parcel: Parcel, db: Session) -> PublicParcelOut:
    """Build the existing approved public parcel projection."""
    upi_normalized = (parcel.upi or "").strip().upper()
    registration_reference = (parcel.registration_reference or "").strip().upper()
    is_synthetic = (
        upi_normalized.startswith("DEMO-UPI-")
        or registration_reference.startswith("DEMO-PARCEL-")
    )

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
            if latest is not None and latest.status == "COMPLETED"
            else ("RESTRICTED" if parcel.status.upper() == "DISPUTED" else "AVAILABLE")
        )
    )

    warning = None
    if unresolved is not None:
        warning_by_status = {
            "PENDING_REVIEW": "PENDING TRANSACTION — NOT AVAILABLE FOR ANOTHER SALE. The ownership transfer is pending and the parcel is unavailable.",
            "PENDING": "PENDING TRANSACTION — NOT AVAILABLE FOR ANOTHER SALE. The ownership transfer is pending and the parcel is unavailable.",
            "UNDER_REVIEW": "UNDER REVIEW — OWNERSHIP TRANSFER NOT YET CONFIRMED. The parcel is not available for another sale.",
            "AWAITING_EVIDENCE": "AWAITING EVIDENCE — OWNERSHIP TRANSFER NOT YET CONFIRMED. The parcel is not available for another sale.",
            "FLAGGED": "FLAGGED — FURTHER INVESTIGATION REQUIRED. The parcel remains restricted pending investigation.",
            "VERIFIED": "VERIFIED — OWNERSHIP TRANSFER PENDING CONFIRMATION. The parcel remains unavailable until the transfer is completed.",
            "APPROVED": "APPROVED — OWNERSHIP TRANSFER PENDING FINAL CONFIRMATION. The parcel remains unavailable until completion is confirmed.",
        }
        warning = warning_by_status.get(unresolved.status)
    elif parcel.status.upper() == "DISPUTED":
        warning = (
            "WARNING: This parcel is currently marked as disputed. "
            "Please consult the official land authority for clarification."
        )

    current_owner = latest_owner(db, parcel.id)
    registered_owner_name = owner_name(db, current_owner.id) if current_owner else None

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
        registered_owner_name=registered_owner_name,
        registered_owner_id=current_owner.id if current_owner else None,
        record_classification=("DEMO_SYNTHETIC" if is_synthetic else "UNVERIFIED_LOCAL_RECORD"),
        official_verification="NOT_INDEPENDENTLY_VERIFIED",
    )


def _find_parcel(db: Session, *, upi: str | None = None, parcel_code: str | None = None) -> Parcel:
    if (upi is None) == (parcel_code is None):
        raise ValueError("Exactly one public parcel identifier is required")
    parcel = (
        db.query(Parcel).filter(Parcel.upi == upi).first()
        if upi is not None
        else db.query(Parcel).filter(Parcel.parcel_code == parcel_code).first()
    )
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.get("/parcels/{upi}", response_model=PublicParcelOut)
def public_parcel_check(upi: str, db: Session = Depends(get_db)):
    """Existing exact UPI lookup kept backward compatible."""
    return _public_parcel_response(_find_parcel(db, upi=upi), db)


@router.get("/parcels/by-code/{parcel_code}", response_model=PublicParcelOut)
def public_parcel_check_by_code(parcel_code: str, db: Session = Depends(get_db)):
    """Exact parcel-code lookup for parcels without an official UPI."""
    return _public_parcel_response(_find_parcel(db, parcel_code=parcel_code), db)
