from sqlalchemy.orm import Session

from app.core.transaction_status import (
    TransactionStatus,
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