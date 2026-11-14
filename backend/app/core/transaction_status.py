from enum import StrEnum


class TransactionStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    COMPLETED = "COMPLETED"

    # Compatibility aliases for legacy records
    PENDING = "PENDING"
    APPROVED = "APPROVED"


ALLOWED_STATUS_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.PENDING_REVIEW: {
        TransactionStatus.UNDER_REVIEW,
    },
    TransactionStatus.PENDING: {
        TransactionStatus.UNDER_REVIEW,
        TransactionStatus.FLAGGED,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.UNDER_REVIEW: {
        TransactionStatus.VERIFIED,
        TransactionStatus.APPROVED,
        TransactionStatus.REJECTED,
        TransactionStatus.FLAGGED,
        TransactionStatus.AWAITING_EVIDENCE,
    },
    TransactionStatus.AWAITING_EVIDENCE: {
        TransactionStatus.UNDER_REVIEW,
    },
    TransactionStatus.FLAGGED: {
        TransactionStatus.UNDER_REVIEW,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.VERIFIED: {
        TransactionStatus.COMPLETED,
    },
    TransactionStatus.APPROVED: {
        TransactionStatus.COMPLETED,
    },
    TransactionStatus.REJECTED: set(),
    TransactionStatus.COMPLETED: set(),
}

# Statuses that represent an unresolved land transaction. While any of these is
# active for a parcel, the parcel must not be presented as available for sale.
UNRESOLVED_STATUSES: tuple[str, ...] = (
    TransactionStatus.PENDING_REVIEW.value,
    TransactionStatus.PENDING.value,
    TransactionStatus.UNDER_REVIEW.value,
    TransactionStatus.AWAITING_EVIDENCE.value,
    TransactionStatus.FLAGGED.value,
    TransactionStatus.VERIFIED.value,
    TransactionStatus.APPROVED.value,
)

FINAL_STATUSES: tuple[str, ...] = (
    TransactionStatus.REJECTED.value,
    TransactionStatus.COMPLETED.value,
)


def is_unresolved(status: TransactionStatus | str) -> bool:
    """Return True while a transaction is still unresolved."""
    return str(status) in UNRESOLVED_STATUSES


def can_transition(
    current: TransactionStatus | str,
    target: TransactionStatus | str,
) -> bool:
    try:
        current_status = TransactionStatus(str(current))
        target_status = TransactionStatus(str(target))
    except ValueError:
        return False
    return target_status in ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
