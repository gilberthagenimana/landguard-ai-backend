"""Notification endpoints for LandGuard AI.

Exposes persisted notifications with filtering, unread counting and read-state
management. Admins receive system-wide alerts; all authenticated users can
manage notifications addressed to themselves.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.domain import NotificationOut, NotificationUnreadCount
from app.services.auth.service import get_current_user, require_roles
from app.services.notification.service import (
    count_unread,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/me", response_model=list[NotificationOut])
def list_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event_type: Optional[str] = Query(default=None, alias="event_type"),
    priority: Optional[str] = Query(default=None, alias="priority"),
    is_read: Optional[bool] = Query(default=None, alias="is_read"),
    q: Optional[str] = Query(default=None, alias="q"),
):
    """List notifications addressed to the authenticated user."""
    items = list_notifications(
        db,
        current_user.id,
        event_type=event_type,
        priority=priority,
        is_read=is_read,
        q=q,
    )
    return [NotificationOut.model_validate(item) for item in items]


@router.get("/me/unread-count", response_model=NotificationUnreadCount)
def get_my_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the unread notification count for the authenticated user."""
    return NotificationUnreadCount(unread_count=count_unread(db, current_user.id))


@router.get("", response_model=list[NotificationOut])
def list_notifications_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
    event_type: Optional[str] = Query(default=None, alias="event_type"),
    priority: Optional[str] = Query(default=None, alias="priority"),
    is_read: Optional[bool] = Query(default=None, alias="is_read"),
    q: Optional[str] = Query(default=None, alias="q"),
):
    """List notifications for the authenticated administrator."""
    items = list_notifications(
        db,
        current_user.id,
        event_type=event_type,
        priority=priority,
        is_read=is_read,
        q=q,
    )
    return [NotificationOut.model_validate(item) for item in items]


@router.get("/unread-count", response_model=NotificationUnreadCount)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    """Return the unread notification count for the authenticated administrator."""
    return NotificationUnreadCount(unread_count=count_unread(db, current_user.id))


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    """Mark a single notification as read for the authenticated administrator."""
    notification = mark_read(db, current_user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationOut.model_validate(notification)


@router.post("/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    """Mark all notifications for the authenticated administrator as read."""
    updated = mark_all_read(db, current_user.id)
    return {"unread_count": count_unread(db, current_user.id), "updated": updated}


@router.post("/me/{notification_id}/read")
def mark_my_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification addressed to the authenticated user as read."""
    notification = mark_read(db, current_user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationOut.model_validate(notification)


@router.post("/me/read-all")
def mark_my_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications addressed to the authenticated user as read."""
    updated = mark_all_read(db, current_user.id)
    return {"unread_count": count_unread(db, current_user.id), "updated": updated}
