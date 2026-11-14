from sqlalchemy.orm import Session

from app.core.transaction_status import (
    TransactionStatus,
    UNRESOLVED_STATUSES,
    can_transition,
)
from app.models.transaction import Transaction


class InvalidTransactionTransition(ValueError):
    """Raised when a transaction status transition is not allowed."""


def transition_transaction(
    db: Session,
    transaction: Transaction,
    target_status: TransactionStatus,
) -> Transaction:
    current_status = TransactionStatus(transaction.status)

    if current_status == target_status:
        return transaction

    if not can_transition(current_status, target_status):
        raise InvalidTransactionTransition(
            f"Cannot transition transaction {transaction.transaction_code} "
            f"from {current_status.value} to {target_status.value}."
        )

    transaction.status = target_status.value
    db.flush()

    return transaction


def get_unresolved_transaction(db: Session, parcel_id: int) -> Transaction | None:
    """Return the latest unresolved transaction for a parcel, if any.

    Unresolved statuses are those that still require review, evidence,
    verification or an ownership transfer before the sale can be finalized.
    """
    return (
        db.query(Transaction)
        .filter(
            Transaction.parcel_id == parcel_id,
            Transaction.status.in_(UNRESOLVED_STATUSES),
        )
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .first()
    )


def get_latest_transaction(db: Session, parcel_id: int) -> Transaction | None:
    """Return the most recent transaction (any status) for a parcel."""
    return (
        db.query(Transaction)
        .filter(Transaction.parcel_id == parcel_id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .first()
    )
