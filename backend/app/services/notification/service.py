"""Admin notification service for LandGuard AI.

Persists admin/security notifications in the active database and exposes
queries for unread counts, listings and read-state updates.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.owner import Owner
from app.models.transaction import Transaction
from app.models.user import User
from app.services.settings.service import get_notification_preferences


NOTIFICATION_DEFAULT_PRIORITY = "medium"


def create_notification(
    db: Session,
    *,
    recipient_user_id: int,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = NOTIFICATION_DEFAULT_PRIORITY,
    related_parcel_upi: Optional[str] = None,
    related_transaction_code: Optional[str] = None,
) -> Notification:
    """Create and persist a notification for a recipient."""
    notification = Notification(
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        title=title,
        description=description,
        priority=priority,
        related_parcel_upi=related_parcel_upi,
        related_transaction_code=related_transaction_code,
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def list_notifications(
    db: Session,
    user_id: int,
    *,
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_read: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 100,
) -> list[Notification]:
    """List notifications for a recipient with optional filters."""
    query = db.query(Notification).filter(Notification.recipient_user_id == user_id)
    if event_type:
        query = query.filter(Notification.event_type == event_type)
    if priority:
        query = query.filter(Notification.priority == priority)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (Notification.title.ilike(like))
            | (Notification.description.ilike(like))
            | (Notification.event_type.ilike(like))
        )
    return (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(max(1, limit))
        .all()
    )


def count_unread(db: Session, user_id: int) -> int:
    """Return the number of unread notifications for a recipient."""
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.recipient_user_id == user_id, Notification.is_read == False)  # noqa: E712
        .scalar()
        or 0
    )


def mark_read(db: Session, user_id: int, notification_id: int) -> Optional[Notification]:
    """Mark a notification as read for its recipient."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.recipient_user_id == user_id,
        )
        .first()
    )
    if not notification or notification.is_read:
        return notification
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    return notification


def mark_all_read(db: Session, user_id: int) -> int:
    """Mark all notifications for a recipient as read. Returns affected count."""
    notifications = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == user_id, Notification.is_read == False)  # noqa: E712
        .all()
    )
    for notification in notifications:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
    if notifications:
        db.commit()
    return len(notifications)


def get_admin_recipient_ids(db: Session) -> list[int]:
    """Return active user ids that hold the ADMIN role."""
    admin_ids: list[int] = []
    for user in db.query(User).all():
        roles = getattr(user, "roles", None) or []
        if user.is_active and any(getattr(role, "name", None) == "ADMIN" for role in roles):
            admin_ids.append(user.id)
    return admin_ids


def notify_admins(
    db: Session,
    *,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = NOTIFICATION_DEFAULT_PRIORITY,
    related_parcel_upi: Optional[str] = None,
    related_transaction_code: Optional[str] = None,
    auto_commit: bool = True,
) -> list[Notification]:
    """Create admin notifications for a business/security event."""
    preferences = get_notification_preferences(db)
    if not preferences.get("in_app_system_alerts", True):
        # In-app alerts can be switched off; security monitoring and audit logs
        # remain fully independent of this preference.
        return []

    notifications: list[Notification] = []
    for recipient_user_id in get_admin_recipient_ids(db):
        # Prevent duplicate notifications for identical events within a short window.
        duplicate = (
            db.query(Notification.id)
            .filter(
                Notification.recipient_user_id == recipient_user_id,
                Notification.event_type == event_type,
                Notification.title == title,
                Notification.created_at >= datetime.utcnow() - timedelta(minutes=30),
            )
            .first()
        )
        if duplicate is not None:
            continue
        notifications.append(
            create_notification(
                db,
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                title=title,
                description=description,
                priority=priority,
                related_parcel_upi=related_parcel_upi,
                related_transaction_code=related_transaction_code,
            )
        )
    if notifications and auto_commit:
        db.commit()
    return notifications


def get_officer_recipient_id(db: Session, transaction_id: int) -> Optional[int]:
    """Resolve the officer (user) who created the transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    return transaction.created_by if transaction else None


def get_user_recipient_id_by_email(db: Session, email: Optional[str]) -> Optional[int]:
    """Resolve a recipient user by email address."""
    if not email:
        return None
    user = db.query(User).filter(User.email.ilike(email.strip())).first()
    return user.id if user else None


def notify_users(
    db: Session,
    *,
    recipient_user_ids: list[int],
    event_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = NOTIFICATION_DEFAULT_PRIORITY,
    related_parcel_upi: Optional[str] = None,
    related_transaction_code: Optional[str] = None,
    auto_commit: bool = True,
) -> list[Notification]:
    """Create notifications for an explicit list of recipient user ids."""
    notifications: list[Notification] = []
    for recipient_user_id in recipient_user_ids:
        if recipient_user_id is None:
            continue
        duplicate = (
            db.query(Notification.id)
            .filter(
                Notification.recipient_user_id == recipient_user_id,
                Notification.event_type == event_type,
                Notification.title == title,
                Notification.created_at >= datetime.utcnow() - timedelta(minutes=30),
            )
            .first()
        )
        if duplicate is not None:
            continue
        notifications.append(
            create_notification(
                db,
                recipient_user_id=recipient_user_id,
                event_type=event_type,
                title=title,
                description=description,
                priority=priority,
                related_parcel_upi=related_parcel_upi,
                related_transaction_code=related_transaction_code,
            )
        )
    if notifications and auto_commit:
        db.commit()
    return notifications


def notify_transaction_parties(
    db: Session,
    transaction_id: int,
    *,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = NOTIFICATION_DEFAULT_PRIORITY,
    related_parcel_upi: Optional[str] = None,
    related_transaction_code: Optional[str] = None,
    auto_commit: bool = True,
    include_seller: bool = False,
) -> list[Notification]:
    """Notify administrators, the responsible officer and optionally the seller."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        return []
    recipient_ids: list[int] = list(get_admin_recipient_ids(db))
    officer_id = transaction.created_by
    if officer_id is not None and officer_id not in recipient_ids:
        recipient_ids.append(officer_id)
    if include_seller and transaction.seller_owner_id is not None:
        seller_owner = db.query(Owner).filter(Owner.id == transaction.seller_owner_id).first()
        seller_user_id = get_user_recipient_id_by_email(db, seller_owner.email if seller_owner else None)
        if seller_user_id is not None and seller_user_id not in recipient_ids:
            recipient_ids.append(seller_user_id)
    return notify_users(
        db,
        recipient_user_ids=recipient_ids,
        event_type=event_type,
        title=title,
        description=description,
        priority=priority,
        related_parcel_upi=related_parcel_upi,
        related_transaction_code=related_transaction_code,
        auto_commit=auto_commit,
    )


def notify_transfer_parties(
    db: Session,
    transaction: Transaction,
    *,
    event_type: str,
    title: str,
    description: Optional[str] = None,
    priority: str = NOTIFICATION_DEFAULT_PRIORITY,
    related_parcel_upi: Optional[str] = None,
    related_transaction_code: Optional[str] = None,
    auto_commit: bool = True,
) -> list[Notification]:
    """Notify administrators and the confirmed buyer for ownership transfers."""
    recipient_ids: list[int] = list(get_admin_recipient_ids(db))
    buyer_owner = db.query(Owner).filter(Owner.id == transaction.buyer_owner_id).first()
    buyer_user_id = get_user_recipient_id_by_email(db, buyer_owner.email if buyer_owner else None)
    if buyer_user_id is not None and buyer_user_id not in recipient_ids:
        recipient_ids.append(buyer_user_id)
    return notify_users(
        db,
        recipient_user_ids=recipient_ids,
        event_type=event_type,
        title=title,
        description=description,
        priority=priority,
        related_parcel_upi=related_parcel_upi,
        related_transaction_code=related_transaction_code,
        auto_commit=auto_commit,
    )
