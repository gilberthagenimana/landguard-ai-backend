
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.schemas.notification_preference import NotificationPreferenceUpdate
from app.services.notification.preferences import (
    get_or_create_preferences,
    update_preferences,
)


@pytest.fixture
def preferences_engine(tmp_path):
    database_path = tmp_path / "preferences_test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}"
    )

    NotificationPreference.__table__.create(engine)

    yield engine

    engine.dispose()


def test_new_user_gets_default_preferences(preferences_engine):
    with Session(preferences_engine) as db:
        preferences = get_or_create_preferences(db, user_id=101)

        assert preferences.user_id == 101
        assert preferences.email_enabled is True
        assert preferences.sms_enabled is True
        assert preferences.in_app_enabled is True
        assert preferences.frequency == "instant"


def test_user_can_update_notification_preferences(preferences_engine):
    data = {
        "email_enabled": False,
        "sms_enabled": False,
        "in_app_enabled": True,
        "frequency": "daily",
    }

    with Session(preferences_engine) as db:
        updated = update_preferences(
            db,
            user_id=101,
            data=data,
        )

        assert updated.email_enabled is False
        assert updated.sms_enabled is False
        assert updated.in_app_enabled is True
        assert updated.frequency == "daily"


def test_preferences_persist_after_database_session_closes(
    preferences_engine,
):
    data = {
        "email_enabled": False,
        "sms_enabled": True,
        "in_app_enabled": False,
        "frequency": "weekly",
    }

    with Session(preferences_engine) as db:
        update_preferences(db, user_id=101, data=data)

    with Session(preferences_engine) as db:
        saved = get_or_create_preferences(db, user_id=101)

        assert saved.email_enabled is False
        assert saved.sms_enabled is True
        assert saved.in_app_enabled is False
        assert saved.frequency == "weekly"


def test_users_have_separate_preferences(preferences_engine):
    with Session(preferences_engine) as db:
        update_preferences(
            db,
            user_id=101,
            data={
                "email_enabled": False,
                "sms_enabled": False,
                "in_app_enabled": False,
                "frequency": "daily",
            },
        )

        user_two = get_or_create_preferences(db, user_id=202)

        assert user_two.email_enabled is True
        assert user_two.sms_enabled is True
        assert user_two.in_app_enabled is True
        assert user_two.frequency == "instant"

        user_one = get_or_create_preferences(db, user_id=101)

        assert user_one.email_enabled is False
        assert user_one.frequency == "daily"


@pytest.mark.parametrize(
    "frequency",
    ["instant", "daily", "weekly"],
)
def test_supported_frequencies_are_valid(frequency):
    preferences = NotificationPreferenceUpdate(
        email_enabled=True,
        sms_enabled=True,
        in_app_enabled=True,
        frequency=frequency,
    )

    assert preferences.frequency == frequency


def test_invalid_frequency_is_rejected():
    with pytest.raises(ValidationError):
        NotificationPreferenceUpdate(
            email_enabled=True,
            sms_enabled=True,
            in_app_enabled=True,
            frequency="monthly",
        )
