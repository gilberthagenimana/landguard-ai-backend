"""Transactional outbox worker for notification emails.

The worker claims a row and commits that claim before SMTP is called. This
keeps database transactions short and gives the system safe at-least-once
delivery semantics when a process crashes after SMTP accepts a message.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import case, or_, update
from sqlalchemy.orm import Session

from app.models.notification_delivery import NotificationDelivery
from app.services.notification.email import send_email

MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 60 * 60
STALE_SENDING_SECONDS = 15 * 60


def _recover_stale_deliveries(db: Session, now: datetime) -> None:
    """Recover abandoned claims, terminalizing those that exhausted retries."""
    stale_before = now - timedelta(seconds=STALE_SENDING_SECONDS)
    stale_deliveries = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.status == "sending",
            NotificationDelivery.updated_at < stale_before,
        )
        .with_for_update(skip_locked=True)
        .all()
    )
    for delivery in stale_deliveries:
        message = "Worker claim expired"
        if delivery.last_error:
            message = f"{delivery.last_error}; {message}"
        delivery.last_error = message
        delivery.claim_token = None
        delivery.updated_at = now
        if delivery.attempt_count >= MAX_ATTEMPTS:
            delivery.status = "failed"
            delivery.next_attempt_at = None
        else:
            delivery.status = "pending"
            delay = min(
                RETRY_MAX_SECONDS,
                RETRY_BASE_SECONDS * (2 ** max(0, delivery.attempt_count - 1)),
            )
            delivery.next_attempt_at = now + timedelta(seconds=delay)


def _claim_one(db: Session, now: datetime) -> Optional[tuple[int, str, str, str, str]]:
    """Claim one eligible delivery and commit before returning it."""
    _recover_stale_deliveries(db, now)
    delivery = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.status.in_(["pending", "failed"]),
            or_(
                NotificationDelivery.next_attempt_at.is_(None),
                NotificationDelivery.next_attempt_at <= now,
            ),
            NotificationDelivery.attempt_count < MAX_ATTEMPTS,
        )
        .order_by(NotificationDelivery.created_at.asc(), NotificationDelivery.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if delivery is None:
        db.commit()
        return None

    delivery.status = "sending"
    delivery.attempt_count += 1
    delivery.last_error = None
    delivery.next_attempt_at = None
    delivery.claim_token = str(uuid4())
    claimed = (
        delivery.id,
        delivery.recipient_email,
        delivery.subject,
        delivery.body,
        delivery.claim_token,
    )
    db.commit()
    return claimed


def _mark_sent(db: Session, delivery_id: int, claim_token: str, now: datetime) -> None:
    result = db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.status == "sending",
            NotificationDelivery.claim_token == claim_token,
        )
        .values(
            status="sent",
            sent_at=now,
            next_attempt_at=None,
            last_error=None,
            claim_token=None,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return
    db.commit()


def _mark_failed(
    db: Session,
    delivery_id: int,
    claim_token: str,
    error: Exception,
    now: datetime,
) -> None:
    last_error = str(error)[:4000]
    retry_at = case(
        (NotificationDelivery.attempt_count >= MAX_ATTEMPTS, None),
        (
            NotificationDelivery.attempt_count == 1,
            now + timedelta(seconds=RETRY_BASE_SECONDS),
        ),
        (
            NotificationDelivery.attempt_count == 2,
            now + timedelta(seconds=RETRY_BASE_SECONDS * 2),
        ),
        (
            NotificationDelivery.attempt_count == 3,
            now + timedelta(seconds=RETRY_BASE_SECONDS * 4),
        ),
        (
            NotificationDelivery.attempt_count == 4,
            now + timedelta(seconds=RETRY_BASE_SECONDS * 8),
        ),
        else_=now + timedelta(seconds=RETRY_MAX_SECONDS),
    )
    result = db.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.status == "sending",
            NotificationDelivery.claim_token == claim_token,
        )
        .values(
            status=case(
                (NotificationDelivery.attempt_count >= MAX_ATTEMPTS, "failed"),
                else_="pending",
            ),
            last_error=last_error,
            next_attempt_at=retry_at,
            claim_token=None,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return
    db.commit()


def dispatch_pending_deliveries(db: Session, *, limit: int = 50) -> int:
    """Send up to ``limit`` queued emails and return the number attempted.

    Pass a dedicated worker session to this function. Each claim and result is
    committed independently, and SMTP is never called inside an open claim
    transaction.
    """
    attempted = 0
    for _ in range(max(0, limit)):
        claimed = _claim_one(db, datetime.utcnow())
        if claimed is None:
            break
        delivery_id, recipient_email, subject, body, claim_token = claimed
        attempted += 1
        try:
            send_email(recipient_email, subject, body)
        except Exception as exc:  # SMTP/provider errors are retryable.
            db.rollback()
            _mark_failed(db, delivery_id, claim_token, exc, datetime.utcnow())
        else:
            _mark_sent(db, delivery_id, claim_token, datetime.utcnow())
    return attempted
