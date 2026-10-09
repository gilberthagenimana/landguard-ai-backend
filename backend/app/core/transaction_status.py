from enum import StrEnum


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    FLAGGED = "FLAGGED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


ALLOWED_STATUS_TRANSITIONS: dict[TransactionStatus, set[TransactionStatus]] = {
    TransactionStatus.PENDING: {
        TransactionStatus.UNDER_REVIEW,
        TransactionStatus.FLAGGED,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.UNDER_REVIEW: {
        TransactionStatus.FLAGGED,
        TransactionStatus.APPROVED,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.FLAGGED: {
        TransactionStatus.UNDER_REVIEW,
        TransactionStatus.REJECTED,
    },
    TransactionStatus.APPROVED: {
        TransactionStatus.COMPLETED,
    },
    TransactionStatus.REJECTED: set(),
    TransactionStatus.COMPLETED: set(),
}


def can_transition(
    current: TransactionStatus,
    target: TransactionStatus,
) -> bool:
    return target in ALLOWED_STATUS_TRANSITIONS.get(current, set())