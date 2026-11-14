"""Tests for the Admin notification system."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.notification import Notification
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.system_config import SystemConfig
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth.service import create_auth_token
from app.services.notification.service import create_notification, notify_admins, notify_transfer_parties
from app.services.settings.service import save_setting

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _setup_data():
    db = TestingSessionLocal()
    roles = {
        name: Role(name=name, description=name.title())
        for name in ("ADMIN", "OFFICER", "AUDITOR")
    }
    db.add_all(roles.values())
    db.flush()
    officer = User(
        username="tx-officer", full_name="TX Officer", email="tx-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[roles["OFFICER"]],
    )
    admin = User(
        username="tx-admin", full_name="TX Admin", email="tx-admin@test.local",
        password_hash=hash_password("AdminPass123!"), is_active=True, roles=[roles["ADMIN"]],
    )
    auditor = User(
        username="tx-auditor", full_name="TX Auditor", email="tx-auditor@test.local",
        password_hash=hash_password("AuditorPass123!"), is_active=True, roles=[roles["AUDITOR"]],
    )
    db.add_all([officer, admin, auditor])
    db.flush()
    seller = Owner(owner_code="OWN-TX-001", full_name="Seller One", status="ACTIVE")
    buyer = Owner(owner_code="OWN-TX-002", full_name="Buyer One", status="ACTIVE")
    parcel = Parcel(
        upi="UPI-TX-001", parcel_code="RW-TX-001", location="Test Location", province="Kigali",
        district="Gasabo", sector="Kacyiru", cell="Cell", village="Village", area_ha=1.0, status="ACTIVE",
    )
    db.add_all([seller, buyer, parcel])
    db.flush()
    db.add(OwnershipHistory(
        parcel_id=parcel.id,
        new_owner_id=seller.id,
        transfer_date=datetime.utcnow() - timedelta(days=365),
        reason_type="FIRST_REGISTRATION",
        supporting_reference="TEST-INITIAL-REGISTRATION",
    ))
    db.commit()
    ids = {
        "token": create_auth_token(officer, role="OFFICER"),
        "admin_token": create_auth_token(admin, role="ADMIN"),
        "auditor_token": create_auth_token(auditor, role="AUDITOR"),
        "parcel_id": parcel.id,
        "seller_id": seller.id,
        "buyer_id": buyer.id,
    }
    db.close()
    return ids


def _create_notification_for_admin(
    event_type: str,
    title: str,
    *,
    priority: str = "medium",
    related_transaction_code: str | None = None,
    related_parcel_upi: str | None = None,
) -> Notification:
    db = TestingSessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "tx-admin").first()
        notification = create_notification(
            db,
            recipient_user_id=admin_user.id,
            event_type=event_type,
            title=title,
            description="Test notification description.",
            priority=priority,
            related_parcel_upi=related_parcel_upi,
            related_transaction_code=related_transaction_code,
        )
        return notification
    finally:
        db.close()


def test_admin_can_list_notifications(client):
    ids = _setup_data()
    notification = _create_notification_for_admin(
        "TRANSACTION_CREATED",
        "New Transaction Awaiting Administrative Review",
        related_transaction_code="TX-777",
    )

    response = client.get("/api/notifications", headers={"Authorization": f"Bearer {ids['admin_token']}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == notification.id
    assert data[0]["event_type"] == "TRANSACTION_CREATED"
    assert data[0]["title"] == "New Transaction Awaiting Administrative Review"
    assert data[0]["related_transaction_code"] == "TX-777"
    assert data[0]["is_read"] is False


def test_admin_unread_count_mark_read_and_mark_all_read(client):
    ids = _setup_data()
    first = _create_notification_for_admin("TRANSACTION_CREATED", "New Transaction Awaiting Administrative Review")
    second = _create_notification_for_admin(
        "TRANSACTION_VERIFIED", "Transaction Verified", priority="high"
    )

    unread_response = client.get(
        "/api/notifications/unread-count", headers={"Authorization": f"Bearer {ids['admin_token']}"}
    )
    assert unread_response.status_code == 200
    assert unread_response.json()["unread_count"] == 2

    mark_all_response = client.post(
        "/api/notifications/mark-all-read", headers={"Authorization": f"Bearer {ids['admin_token']}"}
    )
    assert mark_all_response.status_code == 200
    assert mark_all_response.json()["updated"] >= 2

    unread_response = client.get(
        "/api/notifications/unread-count", headers={"Authorization": f"Bearer {ids['admin_token']}"}
    )
    assert unread_response.json()["unread_count"] == 0

    mark_read_response = client.post(
        f"/api/notifications/{first.id}/read", headers={"Authorization": f"Bearer {ids['admin_token']}"}
    )
    assert mark_read_response.status_code == 200
    marked = mark_read_response.json()
    assert marked["is_read"] is True
    assert marked["read_at"] is not None


def test_notification_filters(client):
    ids = _setup_data()
    _create_notification_for_admin(
        "TRANSACTION_CREATED",
        "New Transaction Awaiting Administrative Review",
        priority="medium",
        related_transaction_code="TX-111",
    )
    _create_notification_for_admin(
        "HIGH_AI_FRAUD_RISK_DETECTED",
        "High AI Fraud Risk Detected",
        priority="high",
        related_transaction_code="TX-222",
    )
    _create_notification_for_admin(
        "PARCEL_REGISTERED",
        "New Parcel Registered",
        priority="low",
        related_parcel_upi="UPI-PARCEL-1",
    )

    headers = {"Authorization": f"Bearer {ids['admin_token']}"}

    response = client.get(
        "/api/notifications", params={"event_type": "HIGH_AI_FRAUD_RISK_DETECTED"}, headers=headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["priority"] == "high"

    response = client.get("/api/notifications", params={"priority": "low"}, headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["event_type"] == "PARCEL_REGISTERED"

    response = client.get("/api/notifications", params={"is_read": False}, headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 3

    response = client.get("/api/notifications", params={"q": "fraud"}, headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["event_type"] == "HIGH_AI_FRAUD_RISK_DETECTED"


def test_officer_and_auditor_cannot_access_admin_notifications(client):
    ids = _setup_data()
    for token_key in ("token", "auditor_token"):
        list_response = client.get(
            "/api/notifications", headers={"Authorization": f"Bearer {ids[token_key]}"}
        )
        assert list_response.status_code == 403

        unread_response = client.get(
            "/api/notifications/unread-count", headers={"Authorization": f"Bearer {ids[token_key]}"}
        )
        assert unread_response.status_code == 403

        mark_all_response = client.post(
            "/api/notifications/mark-all-read", headers={"Authorization": f"Bearer {ids[token_key]}"}
        )
        assert mark_all_response.status_code == 403


def test_unauthenticated_cannot_access_admin_notifications(client):
    list_response = client.get("/api/notifications")
    assert list_response.status_code == 401

    unread_response = client.get("/api/notifications/unread-count")
    assert unread_response.status_code == 401

    mark_all_response = client.post("/api/notifications/mark-all-read")
    assert mark_all_response.status_code == 401


def test_transaction_creation_creates_admin_notification(client):
    ids = _setup_data()
    response = client.post(
        "/api/transactions",
        headers={"Authorization": f"Bearer {ids['token']}"},
        json={
            "parcel_id": ids["parcel_id"],
            "seller_owner_id": ids["seller_id"],
            "buyer_owner_id": ids["buyer_id"],
            "transaction_type": "SALE",
            "transaction_date": datetime.utcnow().isoformat(),
            "declared_value": "15000000",
            "status": "PENDING",
        },
    )
    assert response.status_code == 201
    transaction_code = response.json()["transaction_code"]

    list_response = client.get(
        "/api/notifications",
        params={"event_type": "TRANSACTION_CREATED"},
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data) == 1
    assert data[0]["related_transaction_code"] == transaction_code
    assert data[0]["priority"] == "medium"


def test_verified_review_decision_creates_notification(client):
    ids = _setup_data()
    create_response = client.post(
        "/api/transactions",
        headers={"Authorization": f"Bearer {ids['token']}"},
        json={
            "parcel_id": ids["parcel_id"],
            "seller_owner_id": ids["seller_id"],
            "buyer_owner_id": ids["buyer_id"],
            "transaction_type": "SALE",
            "transaction_date": datetime.utcnow().isoformat(),
            "declared_value": "15000000",
            "status": "PENDING",
        },
    )
    assert create_response.status_code == 201
    transaction_id = create_response.json()["id"]

    status_response = client.put(
        f"/api/transactions/{transaction_id}/status",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={"status": "UNDER_REVIEW", "reason": "Initial administrative review"},
    )
    assert status_response.status_code == 200

    decision_response = client.post(
        f"/api/transactions/{transaction_id}/review-decision",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={
            "action": "VERIFY",
            "explanation": "Ownership records confirm the transfer against the registry.",
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["status"] == "VERIFIED"

    list_response = client.get(
        "/api/notifications", params={"event_type": "TRANSACTION_VERIFIED"}, headers={"Authorization": f"Bearer {ids['admin_token']}"}
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["related_transaction_code"] == create_response.json()["transaction_code"]


def _ensure_admin(db):
    admin_role = db.query(Role).filter(Role.name == "ADMIN").first()
    if admin_role is None:
        admin_role = Role(name="ADMIN", description="Administrator")
        db.add(admin_role)
        db.flush()
    admin = User(
        username="pref-admin",
        full_name="Pref Admin",
        email="pref-admin@test.local",
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
        roles=[admin_role],
    )
    db.add(admin)
    db.flush()
    return admin


def test_notify_admins_respects_in_app_alerts_setting(db_session):
    db = db_session
    admin = _ensure_admin(db)

    save_setting(db, "notifications.in_app_system_alerts", "false")

    notifications = notify_admins(
        db,
        event_type="PARCEL_REGISTERED",
        title="New Parcel Registered",
        description="A new land parcel has been registered in the system.",
        priority="low",
        related_parcel_upi="UPI-PREF-1",
    )
    assert notifications == []

    save_setting(db, "notifications.in_app_system_alerts", "true")
    notifications = notify_admins(
        db,
        event_type="PARCEL_REGISTERED",
        title="New Parcel Registered",
        description="A new land parcel has been registered in the system.",
        priority="low",
        related_parcel_upi="UPI-PREF-1",
    )
    assert len(notifications) == 1


def test_notify_admins_prevents_duplicates(db_session):
    db = db_session
    admin = _ensure_admin(db)

    first = notify_admins(
        db,
        event_type="TRANSACTION_CREATED",
        title="New Transaction Awaiting Administrative Review",
        description="A new land transaction has been registered and is awaiting administrative review.",
        priority="medium",
        related_transaction_code="TX-DUP-001",
    )
    second = notify_admins(
        db,
        event_type="TRANSACTION_CREATED",
        title="New Transaction Awaiting Administrative Review",
        description="A new land transaction has been registered and is awaiting administrative review.",
        priority="medium",
        related_transaction_code="TX-DUP-001",
    )
    assert len(first) == 1
    assert second == []

    third = notify_admins(
        db,
        event_type="TRANSACTION_VERIFIED",
        title="Transaction Verified",
        description="An administrative review verified a land transaction.",
        priority="high",
        related_transaction_code="TX-DUP-001",
    )
    assert len(third) == 1


def test_transaction_creation_notifies_admin_and_responsible_officer(client):
    ids = _setup_data()
    response = client.post(
        "/api/transactions",
        headers={"Authorization": f"Bearer {ids['token']}"},
        json={
            "parcel_id": ids["parcel_id"],
            "seller_owner_id": ids["seller_id"],
            "buyer_owner_id": ids["buyer_id"],
            "transaction_type": "SALE",
            "transaction_date": datetime.utcnow().isoformat(),
            "declared_value": "15000000",
            "status": "PENDING",
        },
    )
    assert response.status_code == 201
    transaction_code = response.json()["transaction_code"]

    db = TestingSessionLocal()
    try:
        officer_user = db.query(User).filter(User.username == "tx-officer").first()
        assert officer_user is not None
        officer_notifications = (
            db.query(Notification)
            .filter(
                Notification.recipient_user_id == officer_user.id,
                Notification.event_type == "TRANSACTION_CREATED",
            )
            .all()
        )
        assert len(officer_notifications) == 1
        assert officer_notifications[0].related_transaction_code == transaction_code
    finally:
        db.close()

    admin_list_response = client.get(
        "/api/notifications",
        params={"event_type": "TRANSACTION_CREATED"},
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
    )
    assert admin_list_response.status_code == 200
    assert len(admin_list_response.json()) == 1
    assert admin_list_response.json()[0]["related_transaction_code"] == transaction_code


def test_official_transfer_confirmation_notifies_admin_and_buyer(db_session):
    db = db_session
    admin = _ensure_admin(db)

    buyer_role = db.query(Role).filter(Role.name == "BUYER").first()
    if buyer_role is None:
        buyer_role = Role(name="BUYER", description="Buyer")
        db.add(buyer_role)
        db.flush()

    buyer_user = User(
        username="tx-buyer",
        full_name="TX Buyer",
        email="tx-buyer@test.local",
        password_hash=hash_password("BuyerPass123!"),
        is_active=True,
        roles=[buyer_role],
    )
    seller_owner = Owner(
        owner_code="OWN-TX-003", full_name="Seller Two", status="ACTIVE", email="seller-two@test.local"
    )
    buyer_owner = Owner(
        owner_code="OWN-TX-004", full_name="Buyer Two", status="ACTIVE", email="tx-buyer@test.local"
    )
    parcel = Parcel(
        upi="UPI-TX-002", parcel_code="RW-TX-002", location="Test Location", province="Kigali",
        district="Gasabo", sector="Kacyiru", cell="Cell", village="Village", area_ha=1.0, status="ACTIVE",
    )
    db.add_all([buyer_user, seller_owner, buyer_owner, parcel])
    db.flush()
    db.add(OwnershipHistory(
        parcel_id=parcel.id,
        new_owner_id=seller_owner.id,
        transfer_date=datetime.utcnow() - timedelta(days=365),
        reason_type="FIRST_REGISTRATION",
        supporting_reference="TEST-INITIAL-REGISTRATION",
    ))
    db.flush()

    transaction = Transaction(
        transaction_code="TX-TRANSFER-001",
        created_by=admin.id,
        parcel_id=parcel.id,
        seller_owner_id=seller_owner.id,
        buyer_owner_id=buyer_owner.id,
        transaction_type="SALE",
        transaction_date=datetime.utcnow(),
        status="VERIFIED",
    )
    db.add(transaction)
    db.flush()

    notifications = notify_transfer_parties(
        db,
        transaction,
        event_type="OWNERSHIP_TRANSFER_CONFIRMED",
        title="Official Ownership Transfer Confirmed",
        description="An official land ownership transfer was confirmed and completed.",
        priority="high",
        related_transaction_code=transaction.transaction_code,
        auto_commit=False,
    )

    buyer_notifications = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == buyer_user.id,
            Notification.event_type == "OWNERSHIP_TRANSFER_CONFIRMED",
        )
        .all()
    )
    assert len(buyer_notifications) == 1
    admin_notifications = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == admin.id, Notification.event_type == "OWNERSHIP_TRANSFER_CONFIRMED")
        .all()
    )
    assert len(admin_notifications) == 1
    assert len(notifications) == 2

    duplicates = notify_transfer_parties(
        db,
        transaction,
        event_type="OWNERSHIP_TRANSFER_CONFIRMED",
        title="Official Ownership Transfer Confirmed",
        description="An official land ownership transfer was confirmed and completed.",
        priority="high",
        related_transaction_code=transaction.transaction_code,
        auto_commit=False,
    )
    assert duplicates == []


def test_user_scoped_notification_endpoints(client):
    ids = _setup_data()
    create_response = client.post(
        "/api/transactions",
        headers={"Authorization": f"Bearer {ids['token']}"},
        json={
            "parcel_id": ids["parcel_id"],
            "seller_owner_id": ids["seller_id"],
            "buyer_owner_id": ids["buyer_id"],
            "transaction_type": "SALE",
            "transaction_date": datetime.utcnow().isoformat(),
            "declared_value": "15000000",
            "status": "PENDING",
        },
    )
    assert create_response.status_code == 201

    my_list_response = client.get(
        "/api/notifications/me", headers={"Authorization": f"Bearer {ids['token']}"}
    )
    assert my_list_response.status_code == 200
    data = my_list_response.json()
    assert len(data) == 1
    assert data[0]["event_type"] == "TRANSACTION_CREATED"

    my_unread_response = client.get(
        "/api/notifications/me/unread-count", headers={"Authorization": f"Bearer {ids['token']}"}
    )
    assert my_unread_response.status_code == 200
    assert my_unread_response.json()["unread_count"] == 1

    mark_all_response = client.post(
        "/api/notifications/me/read-all", headers={"Authorization": f"Bearer {ids['token']}"}
    )
    assert mark_all_response.status_code == 200
    assert mark_all_response.json()["updated"] == 1

    mark_response = client.post(
        f"/api/notifications/me/{data[0]['id']}/read", headers={"Authorization": f"Bearer {ids['token']}"}
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["is_read"] is True

    unauthenticated_response = client.get("/api/notifications/me")
    assert unauthenticated_response.status_code == 401


def test_user_cannot_mark_other_users_notification_as_read(client):
    ids = _setup_data()
    notification = _create_notification_for_admin("PARCEL_REGISTERED", "New Parcel Registered")

    mark_response = client.post(
        f"/api/notifications/me/{notification.id}/read", headers={"Authorization": f"Bearer {ids['token']}"}
    )
    assert mark_response.status_code == 404
