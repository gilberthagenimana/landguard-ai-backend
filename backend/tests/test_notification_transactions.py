import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.services.notification.service import (
    create_notification,
    mark_read,
    mark_all_read,
    notify_users,
)


@pytest.fixture
def test_engine(tmp_path):
    database_path = tmp_path / "notifications_test.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{database_path}"
    )

    Notification.__table__.create(engine)

    yield engine

    engine.dispose()


def test_create_notification_does_not_commit(test_engine):
    with Session(test_engine) as db:
        notification = create_notification(
            db,
            recipient_user_id=101,
            event_type="TEST_EVENT",
            title="Test notification",
        )

        assert notification.id is not None

        with Session(test_engine) as observer:
            assert observer.query(Notification).count() == 0

        db.rollback()

    with Session(test_engine) as observer:
        assert observer.query(Notification).count() == 0


def test_notify_users_auto_commit_false_can_rollback(test_engine):
    with Session(test_engine) as db:
        notifications = notify_users(
            db,
            recipient_user_ids=[101],
            event_type="TEST_EVENT",
            title="Uncommitted notification",
            auto_commit=False,
        )

        assert len(notifications) == 1

        with Session(test_engine) as observer:
            assert observer.query(Notification).count() == 0

        db.rollback()

    with Session(test_engine) as observer:
        assert observer.query(Notification).count() == 0


def test_notify_users_auto_commit_true_persists(test_engine):
    with Session(test_engine) as db:
        notifications = notify_users(
            db,
            recipient_user_ids=[101],
            event_type="TEST_EVENT",
            title="Committed notification",
            auto_commit=True,
        )

        assert len(notifications) == 1

    with Session(test_engine) as observer:
        assert observer.query(Notification).count() == 1

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_failed_savepoint_does_not_rollback_outer_transaction(test_engine):
    with test_engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE savepoint_probe (
                id INTEGER PRIMARY KEY,
                value TEXT UNIQUE NOT NULL
            )
        """))

    with Session(test_engine) as db:
        db.execute(
            text("INSERT INTO savepoint_probe (value) VALUES (:value)"),
            {"value": "existing"},
        )

        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.execute(
                    text("INSERT INTO savepoint_probe (value) VALUES (:value)"),
                    {"value": "existing"},
                )

        # The outer transaction should still be usable.
        db.execute(
            text("INSERT INTO savepoint_probe (value) VALUES (:value)"),
            {"value": "survives"},
        )
        db.commit()

    with Session(test_engine) as observer:
        values = observer.execute(
            text("SELECT value FROM savepoint_probe ORDER BY id")
        ).scalars().all()

        assert values == ["existing", "survives"]

import app.models  # Register all SQLAlchemy models and relationships.
from app.db.base import Base
from app.models import Owner, Parcel, RiskPrediction, Transaction
from app.services.risk import service as risk_service
from app.services.notification import service as notification_service


@pytest.fixture
def risk_test_engine(tmp_path):
    database_path = tmp_path / "risk_test.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")

    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


class FakeHighRiskModel:
    classes_ = ["LOW", "MEDIUM", "HIGH"]

    def predict(self, frame):
        return ["HIGH"]

    def predict_proba(self, frame):
        return [[0.05, 0.05, 0.90]]


def test_risk_prediction_survives_notification_failures(
    risk_test_engine,
    tmp_path,
    monkeypatch,
):
    model_file = tmp_path / "fake_model.joblib"
    model_file.touch()

    monkeypatch.setattr(
        risk_service,
        "_model_path",
        lambda: model_file,
    )
    monkeypatch.setattr(
        risk_service.joblib,
        "load",
        lambda path: FakeHighRiskModel(),
    )

    notification_attempts = []

    def failing_notification(*args, **kwargs):
        notification_attempts.append(kwargs.get("event_type"))
        raise RuntimeError("Simulated notification failure")

    monkeypatch.setattr(
        notification_service,
        "notify_transaction_parties",
        failing_notification,
    )

    with Session(risk_test_engine) as db:
        seller = Owner(
            owner_code="TEST-OWNER-1",
            full_name="Test Seller",
        )
        buyer = Owner(
            owner_code="TEST-OWNER-2",
            full_name="Test Buyer",
        )

        db.add_all([seller, buyer])
        db.flush()

        parcel = Parcel(
            parcel_code="TEST-PARCEL-1",
            location="Test Location",
            district="Rulindo",
            sector="Bushoki",
            cell="Test Cell",
            village="Test Village",
            area_ha=1.0,
        )
        db.add(parcel)
        db.flush()

        previous_transaction = Transaction(
            transaction_code="TEST-TX-001",
            parcel_id=parcel.id,
            seller_owner_id=seller.id,
            buyer_owner_id=buyer.id,
            transaction_type="SALE",
            status="PENDING",
        )

        current_transaction = Transaction(
            transaction_code="TEST-TX-002",
            parcel_id=parcel.id,
            seller_owner_id=seller.id,
            buyer_owner_id=buyer.id,
            transaction_type="SALE",
            status="PENDING_REVIEW",
            declared_value=1000,
        )

        db.add_all([previous_transaction, current_transaction])
        db.flush()

        result = risk_service.analyze_transaction(
            db,
            current_transaction,
        )

        assert result.risk_level == "HIGH"
        assert len(notification_attempts) == 2

        assert "HIGH_AI_FRAUD_RISK_DETECTED" in notification_attempts
        assert "OWNERSHIP_CONFLICT_DETECTED" in notification_attempts

        assert db.query(RiskPrediction).filter_by(
            transaction_id=current_transaction.id
        ).count() == 1

        # Save the ID before closing the database session.
        current_transaction_id = current_transaction.id

        # Simulate the route's final commit.
        db.commit()

    with Session(risk_test_engine) as observer:
        saved_prediction = observer.query(RiskPrediction).filter_by(
            transaction_id=current_transaction_id
        ).first()

        assert saved_prediction is not None
        assert saved_prediction.risk_level == "HIGH"

def test_same_transaction_notification_is_suppressed(test_engine):
    with Session(test_engine) as db:
        first = notify_users(
            db,
            recipient_user_ids=[1],
            event_type="HIGH_RISK",
            title="High Risk Detected",
            related_transaction_code="TX-001",
        )

        second = notify_users(
            db,
            recipient_user_ids=[1],
            event_type="HIGH_RISK",
            title="High Risk Detected",
            related_transaction_code="TX-001",
        )

        assert len(first) == 1
        assert len(second) == 0
        assert db.query(Notification).count() == 1


def test_different_transactions_receive_separate_notifications(test_engine):
    with Session(test_engine) as db:
        first = notify_users(
            db,
            recipient_user_ids=[1],
            event_type="HIGH_RISK",
            title="High Risk Detected",
            related_transaction_code="TX-001",
        )

        second = notify_users(
            db,
            recipient_user_ids=[1],
            event_type="HIGH_RISK",
            title="High Risk Detected",
            related_transaction_code="TX-002",
        )

        assert len(first) == 1
        assert len(second) == 1
        assert db.query(Notification).count() == 2

def test_user_cannot_mark_another_users_notification_as_read(test_engine):
    with Session(test_engine) as db:
        notification = create_notification(
            db,
            recipient_user_id=1,
            event_type="TEST_EVENT",
            title="Private notification",
        )
        db.commit()

        result = mark_read(
            db,
            user_id=2,
            notification_id=notification.id,
        )

        assert result is None

        saved = db.query(Notification).filter_by(id=notification.id).first()
        assert saved.recipient_user_id == 1
        assert saved.is_read is False


def test_mark_all_read_only_updates_current_users_notifications(test_engine):
    with Session(test_engine) as db:
        first = create_notification(
            db,
            recipient_user_id=1,
            event_type="TEST_EVENT",
            title="User 1 notification",
        )
        second = create_notification(
            db,
            recipient_user_id=2,
            event_type="TEST_EVENT",
            title="User 2 notification",
        )
        db.commit()

        affected = mark_all_read(db, user_id=1)

        assert affected == 1

        db.refresh(first)
        db.refresh(second)

        assert first.is_read is True
        assert second.is_read is False