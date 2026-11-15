from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference


def get_or_create_preferences(
    db: Session,
    user_id: int,
) -> NotificationPreference:
    preferences = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == user_id)
        .first()
    )

    if preferences is None:
        preferences = NotificationPreference(user_id=user_id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)

    return preferences


def update_preferences(
    db: Session,
    user_id: int,
    data: dict,
) -> NotificationPreference:
    preferences = get_or_create_preferences(db, user_id)

    for key, value in data.items():
        setattr(preferences, key, value)

    db.commit()
    db.refresh(preferences)

    return preferences