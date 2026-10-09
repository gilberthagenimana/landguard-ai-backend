"""Tests for transaction CRUD operations."""
from __future__ import annotations

from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.user import User
from app.services.auth.service import create_auth_token

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


def _setup_data():
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="tx-officer", full_name="TX Officer", email="tx-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.flush()
    seller = Owner(owner_code="OWN-TX-001", full_name="Seller One", status="ACTIVE")
    buyer = Owner(owner_code="OWN-TX-002", full_name="Buyer One", status="ACTIVE")
    parcel = Parcel(
        upi="UPI-TX-001", parcel_code="RW-TX-001", location="Test Location", province="Kigali",
        district="Gasabo", sector="Kacyiru", cell="Cell", village="Village", area_ha=1.0, status="ACTIVE",
    )
    db.add_all([seller, buyer, parcel])
    db.commit()
    token = create_auth_token(user)
    ids = {"token": token, "parcel_id": parcel.id, "seller_id": seller.id, "buyer_id": buyer.id}
    db.close()
    return ids


def test_create_transaction_success(client):
    ids = _setup_data()
    response = client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": ids["parcel_id"], "seller_owner_id": ids["seller_id"], "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(),
        "declared_value": "15000000", "status": "PENDING",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["transaction_code"].startswith("TX-")
    assert data["status"] == "PENDING"


def test_create_transaction_nonexistent_parcel(client):
    ids = _setup_data()
    response = client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": 99999, "seller_owner_id": ids["seller_id"], "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(), "status": "PENDING",
    })
    assert response.status_code == 404


def test_create_transaction_nonexistent_seller(client):
    ids = _setup_data()
    response = client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": ids["parcel_id"], "seller_owner_id": 99999, "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(), "status": "PENDING",
    })
    assert response.status_code == 404


def test_list_transactions(client):
    ids = _setup_data()
    client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": ids["parcel_id"], "seller_owner_id": ids["seller_id"], "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(),
        "declared_value": "1000000", "status": "PENDING",
    })
    response = client.get("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_transaction_by_id(client):
    ids = _setup_data()
    create_resp = client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": ids["parcel_id"], "seller_owner_id": ids["seller_id"], "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(),
        "declared_value": "500000", "status": "PENDING",
    })
    tx_id = create_resp.json()["id"]
    response = client.get(f"/api/transactions/{tx_id}", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    assert response.json()["transaction_code"] == create_resp.json()["transaction_code"]


def test_get_nonexistent_transaction(client):
    ids = _setup_data()
    response = client.get("/api/transactions/99999", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 404


def test_stored_verification_empty(client):
    ids = _setup_data()
    create_resp = client.post("/api/transactions", headers={"Authorization": f"Bearer {ids['token']}"}, json={
        "parcel_id": ids["parcel_id"], "seller_owner_id": ids["seller_id"], "buyer_owner_id": ids["buyer_id"],
        "transaction_type": "SALE", "transaction_date": datetime.utcnow().isoformat(),
        "declared_value": "500000", "status": "PENDING",
    })
    tx_id = create_resp.json()["id"]
    response = client.get(f"/api/transactions/{tx_id}/verification", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    assert response.json() == []


def _create_transaction_for_completion(client, ids):
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
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _set_transaction_status(client, ids, transaction_id, new_status):
    return client.put(
        f"/api/transactions/{transaction_id}/status",
        headers={"Authorization": f"Bearer {ids['token']}"},
        json={"status": new_status, "reason": "Regression test"},
    )


def _record_initial_owner(ids, owner_id=None):
    db = TestingSessionLocal()
    try:
        history = OwnershipHistory(
            parcel_id=ids["parcel_id"],
            previous_owner_id=None,
            new_owner_id=owner_id if owner_id is not None else ids["seller_id"],
            transfer_date=datetime.utcnow() - timedelta(days=365),
            reason_type="FIRST_REGISTRATION",
            supporting_reference="TEST-INITIAL-REGISTRATION",
        )
        db.add(history)
        db.commit()
    finally:
        db.close()


def _approve_transaction(client, ids, transaction_id):
    response = _set_transaction_status(
        client, ids, transaction_id, "UNDER_REVIEW"
    )
    assert response.status_code == 200, response.text

    response = _set_transaction_status(
        client, ids, transaction_id, "APPROVED"
    )
    assert response.status_code == 200, response.text


def test_completed_transfer_appends_ownership_history(client):
    ids = _setup_data()
    _record_initial_owner(ids)
    transaction_id = _create_transaction_for_completion(client, ids)
    _approve_transaction(client, ids, transaction_id)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED"
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"

    db = TestingSessionLocal()
    try:
        rows = (
            db.query(OwnershipHistory)
            .filter(OwnershipHistory.parcel_id == ids["parcel_id"])
            .order_by(
                OwnershipHistory.transfer_date.desc(),
                OwnershipHistory.id.desc(),
            )
            .all()
        )
        assert len(rows) == 2
        assert rows[0].previous_owner_id == ids["seller_id"]
        assert rows[0].new_owner_id == ids["buyer_id"]
        assert rows[0].reason_type == "TRANSFER"
        assert rows[0].supporting_reference == (
            db.query(__import__("app.models.transaction", fromlist=["Transaction"]).Transaction)
            .filter_by(id=transaction_id)
            .one()
            .transaction_code
        )
    finally:
        db.close()


def test_completed_transfer_rejects_seller_not_latest_owner(client):
    ids = _setup_data()
    _record_initial_owner(ids, owner_id=ids["buyer_id"])
    transaction_id = _create_transaction_for_completion(client, ids)
    _approve_transaction(client, ids, transaction_id)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED"
    )
    assert response.status_code == 409
    assert "seller does not match" in response.json()["detail"].lower()

    db = TestingSessionLocal()
    try:
        from app.models.transaction import Transaction

        transaction = db.query(Transaction).filter_by(id=transaction_id).one()
        assert transaction.status == "APPROVED"
        assert (
            db.query(OwnershipHistory)
            .filter_by(parcel_id=ids["parcel_id"])
            .count()
            == 1
        )
    finally:
        db.close()


def test_completed_transfer_requires_established_ownership(client):
    ids = _setup_data()
    transaction_id = _create_transaction_for_completion(client, ids)
    _approve_transaction(client, ids, transaction_id)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED"
    )
    assert response.status_code == 409
    assert "ownership is not established" in response.json()["detail"].lower()

    db = TestingSessionLocal()
    try:
        from app.models.transaction import Transaction

        transaction = db.query(Transaction).filter_by(id=transaction_id).one()
        assert transaction.status == "APPROVED"
        assert (
            db.query(OwnershipHistory)
            .filter_by(parcel_id=ids["parcel_id"])
            .count()
            == 0
        )
    finally:
        db.close()


def test_pending_transaction_cannot_jump_to_completed(client):
    ids = _setup_data()
    _record_initial_owner(ids)
    transaction_id = _create_transaction_for_completion(client, ids)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED"
    )
    assert response.status_code == 400

    db = TestingSessionLocal()
    try:
        from app.models.transaction import Transaction

        transaction = db.query(Transaction).filter_by(id=transaction_id).one()
        assert transaction.status == "PENDING"
        assert (
            db.query(OwnershipHistory)
            .filter_by(parcel_id=ids["parcel_id"])
            .count()
            == 1
        )
    finally:
        db.close()
