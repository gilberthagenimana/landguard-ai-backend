from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_preference import NotificationPreference
from app.models.system_config import SystemConfig
from app.models.user import User
from app.services.notification import dispatcher
from app.services.notification.service import create_notification, notify_users
from app.services.settings.service import get_notification_preferences


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'outbox.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            username="outbox-user",
            full_name="Outbox User",
            email="outbox@example.com",
            password_hash="test",
            is_active=True,
        )
        session.add(user)
        session.commit()
        yield session, user.id
    engine.dispose()


def test_instant_enabled_queues_delivery(db):
    session, user_id = db
    notification = create_notification(
        session, recipient_user_id=user_id, event_type="TEST", title="Subject", description="Body"
    )
    delivery = session.query(NotificationDelivery).one()
    assert delivery.notification_id == notification.id
    assert delivery.recipient_email == "outbox@example.com"
    assert delivery.body == "Subject\n\nBody"


@pytest.mark.parametrize("preference", [
    NotificationPreference(email_enabled=False, frequency="instant"),
    NotificationPreference(email_enabled=True, frequency="daily"),
    NotificationPreference(email_enabled=True, frequency="weekly"),
])
def test_disabled_or_digest_preferences_do_not_queue(db, preference):
    session, user_id = db
    preference.user_id = user_id
    session.add(preference)
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    assert session.query(NotificationDelivery).count() == 0


def test_missing_preference_uses_instant_default(db):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    assert session.query(NotificationDelivery).count() == 1


def test_global_notification_preferences_read_does_not_commit(db):
    session, _ = db
    session.add(SystemConfig(key="notifications.frequency", value="weekly"))
    session.flush()

    preferences = get_notification_preferences(session)

    assert preferences["frequency"] == "weekly"
    observer = Session(session.get_bind())
    try:
        assert observer.query(SystemConfig).count() == 0
    finally:
        observer.close()


def test_invalid_email_does_not_queue(db):
    session, user_id = db
    session.query(User).filter(User.id == user_id).one().email = "not-an-email"
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    assert session.query(NotificationDelivery).count() == 0


def test_dispatch_success_marks_sent(db, monkeypatch):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    sent = []
    monkeypatch.setattr(dispatcher, "send_email", lambda *args: sent.append(args))
    assert dispatcher.dispatch_pending_deliveries(session) == 1
    delivery = session.query(NotificationDelivery).one()
    assert delivery.status == "sent"
    assert delivery.sent_at is not None
    assert sent == [("outbox@example.com", "Subject", "Subject")]


def test_dispatch_failure_schedules_retry(db, monkeypatch):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")

    def fail(*args):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(dispatcher, "send_email", fail)
    assert dispatcher.dispatch_pending_deliveries(session) == 1
    delivery = session.query(NotificationDelivery).one()
    assert delivery.status == "pending"
    assert delivery.attempt_count == 1
    assert delivery.last_error == "provider unavailable"
    assert delivery.next_attempt_at > datetime.utcnow()


def test_retry_backoff_uses_expected_delays(db, monkeypatch):
    session, user_id = db

    create_notification(
        session,
        recipient_user_id=user_id,
        event_type="TEST",
        title="Retry test",
    )

    monkeypatch.setattr(
        dispatcher,
        "send_email",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("simulated SMTP failure")
        ),
    )

    expected_delays = [60, 120, 240, 480]

    for expected_attempt, expected_delay in enumerate(expected_delays, start=1):
        delivery = session.query(NotificationDelivery).one()

        # Make the delivery eligible for its next attempt.
        delivery.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
        session.commit()

        before = datetime.utcnow()

        assert dispatcher.dispatch_pending_deliveries(session) == 1

        session.refresh(delivery)

        assert delivery.status == "pending"
        assert delivery.attempt_count == expected_attempt

        actual_delay = (delivery.next_attempt_at - before).total_seconds()
        assert expected_delay - 2 <= actual_delay <= expected_delay + 2

    # Make the fifth attempt eligible.
    delivery = session.query(NotificationDelivery).one()
    delivery.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()

    assert dispatcher.dispatch_pending_deliveries(session) == 1

    session.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.attempt_count == dispatcher.MAX_ATTEMPTS
    assert delivery.next_attempt_at is None


def test_dispatch_stops_at_max_attempts(db, monkeypatch):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    delivery = session.query(NotificationDelivery).one()
    delivery.attempt_count = dispatcher.MAX_ATTEMPTS - 1
    delivery.next_attempt_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    monkeypatch.setattr(dispatcher, "send_email", lambda *args: (_ for _ in ()).throw(RuntimeError("failed")))
    assert dispatcher.dispatch_pending_deliveries(session) == 1
    assert session.query(NotificationDelivery).one().status == "failed"


def test_duplicate_prevention_and_auto_commit_false(db):
    session, user_id = db
    first = notify_users(
        session, recipient_user_ids=[user_id], event_type="TEST", title="Subject", auto_commit=False
    )
    second = notify_users(
        session, recipient_user_ids=[user_id], event_type="TEST", title="Subject", auto_commit=False
    )
    assert len(first) == 1
    assert second == []
    assert session.query(NotificationDelivery).count() == 1
    session.rollback()
    assert session.query(Notification).count() == 0
    assert session.query(NotificationDelivery).count() == 0


def test_stale_delivery_at_max_attempts_becomes_failed(db):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    delivery = session.query(NotificationDelivery).one()
    delivery.status = "sending"
    delivery.attempt_count = dispatcher.MAX_ATTEMPTS
    delivery.claim_token = "expired-token"
    delivery.updated_at = datetime.utcnow() - timedelta(seconds=dispatcher.STALE_SENDING_SECONDS + 1)
    session.commit()

    assert dispatcher._claim_one(session, datetime.utcnow()) is None
    session.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.next_attempt_at is None
    assert delivery.claim_token is None
    assert "Worker claim expired" in delivery.last_error


def test_stale_delivery_below_max_attempts_can_be_retried(db):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    delivery = session.query(NotificationDelivery).one()
    delivery.status = "sending"
    delivery.attempt_count = 1
    delivery.claim_token = "expired-token"
    delivery.updated_at = datetime.utcnow() - timedelta(seconds=dispatcher.STALE_SENDING_SECONDS + 1)
    session.commit()

    recovery_now = datetime.utcnow()
    dispatcher._recover_stale_deliveries(session, recovery_now)
    session.commit()
    claimed = dispatcher._claim_one(
        session, recovery_now + timedelta(seconds=dispatcher.RETRY_BASE_SECONDS + 1)
    )
    assert claimed is not None
    assert claimed[4] != "expired-token"
    session.refresh(delivery)
    assert delivery.status == "sending"
    assert delivery.attempt_count == 2
    assert delivery.claim_token == claimed[4]


def test_old_worker_cannot_overwrite_newer_worker_result(db):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    first_claim = dispatcher._claim_one(session, datetime.utcnow())
    assert first_claim is not None
    delivery_id, _, _, _, old_token = first_claim
    delivery = session.get(NotificationDelivery, delivery_id)
    delivery.updated_at = datetime.utcnow() - timedelta(seconds=dispatcher.STALE_SENDING_SECONDS + 1)
    session.commit()

    recovery_now = datetime.utcnow()
    dispatcher._recover_stale_deliveries(session, recovery_now)
    session.commit()
    second_claim = dispatcher._claim_one(
        session, recovery_now + timedelta(seconds=dispatcher.RETRY_BASE_SECONDS + 1)
    )
    assert second_claim is not None
    new_token = second_claim[4]
    dispatcher._mark_sent(session, delivery_id, old_token, datetime.utcnow())
    session.refresh(delivery)
    assert delivery.status == "sending"
    assert delivery.claim_token == new_token

    dispatcher._mark_sent(session, delivery_id, new_token, datetime.utcnow())
    assert session.get(NotificationDelivery, delivery_id).status == "sent"


def test_active_delivery_is_claimed_only_once(db):
    session, user_id = db
    create_notification(session, recipient_user_id=user_id, event_type="TEST", title="Subject")
    first_claim = dispatcher._claim_one(session, datetime.utcnow())
    assert first_claim is not None

    second_session = Session(session.get_bind())
    try:
        assert dispatcher._claim_one(second_session, datetime.utcnow()) is None
    finally:
        second_session.close()
