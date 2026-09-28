from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.transaction import Transaction
from app.models.verification_result import VerificationResultRecord
from app.schemas.verification import VerificationResult

ACTIVE_TRANSACTION_STATUSES = ("PENDING", "UNDER_REVIEW", "ACTIVE")
RECENT_DAYS = 30
FREQUENCY_THRESHOLD = 2
SUSPICIOUS_CHANGE_THRESHOLD = 2


def _current_owner_id(db: Session, parcel_id: int) -> int | None:
    latest = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == parcel_id)
        .order_by(OwnershipHistory.transfer_date.desc(), OwnershipHistory.id.desc())
        .first()
    )
    return latest.new_owner_id if latest else None


def verify_transaction(db: Session, transaction: Transaction) -> list[VerificationResult]:
    results: list[VerificationResult] = []
    parcel = db.query(Parcel).filter(Parcel.id == transaction.parcel_id).first()
    seller = (
        db.query(Owner).filter(Owner.id == transaction.seller_owner_id).first()
        if transaction.seller_owner_id
        else None
    )
    buyer = (
        db.query(Owner).filter(Owner.id == transaction.buyer_owner_id).first()
        if transaction.buyer_owner_id
        else None
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)

    results.append(
        VerificationResult(
            rule_name="Parcel exists",
            status="PASS" if parcel else "FAIL",
            severity="LOW" if parcel else "HIGH",
            explanation=(
                "The transaction references an existing parcel in the available records."
                if parcel
                else "The transaction references a parcel that is not present in the available records."
            ),
        )
    )

    current_owner_id = _current_owner_id(db, transaction.parcel_id) if parcel else None
    seller_matches = bool(seller and current_owner_id and seller.id == current_owner_id)
    results.append(
        VerificationResult(
            rule_name="Seller ownership match",
            status="PASS" if seller_matches else "FAIL",
            severity="LOW" if seller_matches else "HIGH",
            explanation=(
                "The seller matches the latest recorded owner."
                if seller_matches
                else "The seller does not match the registered owner in the available system records."
            ),
        )
    )

    authorized = bool(seller and seller.status == "ACTIVE" and (not parcel or parcel.status in {"ACTIVE", "REGISTERED"}))
    results.append(
        VerificationResult(
            rule_name="Seller authorization",
            status="PASS" if authorized else "WARNING",
            severity="LOW" if authorized else "HIGH",
            explanation=(
                "The seller and parcel are recorded as active, which supports proceeding with additional checks."
                if authorized
                else "The seller or parcel status does not show the authorization expected from available records. Additional verification is recommended."
            ),
        )
    )

    other_active = (
        db.query(Transaction)
        .filter(
            Transaction.parcel_id == transaction.parcel_id,
            Transaction.id != transaction.id,
            Transaction.status.in_(ACTIVE_TRANSACTION_STATUSES),
        )
        .all()
    )
    results.append(
        VerificationResult(
            rule_name="Active transaction already exists",
            status="FAIL" if other_active else "PASS",
            severity="HIGH" if other_active else "LOW",
            explanation=(
                "Another active transaction already exists for this parcel and should be reviewed before continuing."
                if other_active
                else "No other active transaction was found for this parcel."
            ),
        )
    )

    conflicting = [
        item
        for item in other_active
        if item.buyer_owner_id and item.buyer_owner_id != transaction.buyer_owner_id
    ]
    results.append(
        VerificationResult(
            rule_name="Conflicting transaction records",
            status="FAIL" if conflicting else ("WARNING" if other_active else "PASS"),
            severity="HIGH" if conflicting else ("MEDIUM" if other_active else "LOW"),
            explanation=(
                "Possible duplicate transaction: the same parcel appears in another active record with a different buyer."
                if conflicting
                else (
                    "Another active record exists for this parcel, but buyer details do not currently conflict."
                    if other_active
                    else "No conflicting transaction records were found for this parcel."
                )
            ),
        )
    )

    recent_changes = (
        db.query(OwnershipHistory)
        .filter(
            OwnershipHistory.parcel_id == transaction.parcel_id,
            OwnershipHistory.transfer_date >= recent_cutoff,
        )
        .all()
    )
    results.append(
        VerificationResult(
            rule_name="Recent ownership change",
            status="WARNING" if recent_changes else "PASS",
            severity="MEDIUM" if recent_changes else "LOW",
            explanation=(
                "WARNING: Recent ownership change detected. This is a risk indicator, not proof of fraud."
                if recent_changes
                else "No ownership change was recorded within the last 30 days."
            ),
        )
    )

    inconsistent = not all(
        [
            transaction.parcel_id,
            transaction.transaction_type,
            transaction.status,
            transaction.transaction_date,
            transaction.seller_owner_id,
            transaction.buyer_owner_id,
        ]
    ) or (seller and buyer and seller.id == buyer.id)
    results.append(
        VerificationResult(
            rule_name="Important fields consistent",
            status="FAIL" if inconsistent else "PASS",
            severity="MEDIUM" if inconsistent else "LOW",
            explanation=(
                "Important transaction fields are missing or inconsistent in the available records."
                if inconsistent
                else "Required transaction fields are present and internally consistent."
            ),
        )
    )

    recent_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.parcel_id == transaction.parcel_id,
            Transaction.transaction_date >= recent_cutoff,
        )
        .count()
    )
    unusual_frequency = recent_transactions > FREQUENCY_THRESHOLD
    results.append(
        VerificationResult(
            rule_name="Unusual transaction frequency",
            status="WARNING" if unusual_frequency else "PASS",
            severity="MEDIUM" if unusual_frequency else "LOW",
            explanation=(
                f"This parcel has {recent_transactions} recorded transactions in the last {RECENT_DAYS} days, which is unusual compared with typical demo patterns."
                if unusual_frequency
                else "Transaction frequency for this parcel is within the expected range for the available records."
            ),
        )
    )

    multiple_changes = len(recent_changes) >= SUSPICIOUS_CHANGE_THRESHOLD
    results.append(
        VerificationResult(
            rule_name="Multiple recent ownership changes",
            status="WARNING" if multiple_changes else "PASS",
            severity="HIGH" if multiple_changes else "LOW",
            explanation=(
                "Multiple ownership changes were recorded within a short period and require additional verification."
                if multiple_changes
                else "There are not multiple ownership changes within the recent review window."
            ),
        )
    )

    db.query(VerificationResultRecord).filter(VerificationResultRecord.transaction_id == transaction.id).delete()
    for item in results:
        db.add(
            VerificationResultRecord(
                transaction_id=transaction.id,
                rule_name=item.rule_name,
                result=item.status,
                severity=item.severity,
                explanation=item.explanation,
            )
        )
    db.flush()
    return results
