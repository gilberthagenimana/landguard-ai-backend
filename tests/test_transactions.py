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
from app.models.risk_prediction import RiskPrediction
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth.service import create_auth_token
from app.api.v1.routes import transactions as transaction_routes

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


def _setup_data(include_initial_ownership=True):
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
    if include_initial_ownership:
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
    assert data["status"] == "PENDING_REVIEW"


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
    # Automated verification runs on transaction creation and persists results.
    assert len(response.json()) > 0


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


def _set_transaction_status(client, ids, transaction_id, new_status, token_key="token"):
    return client.put(
        f"/api/transactions/{transaction_id}/status",
        headers={"Authorization": f"Bearer {ids[token_key]}"},
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
    response = _set_transaction_status(client, ids, transaction_id, "UNDER_REVIEW")
    assert response.status_code == 200, response.text

    response = _set_transaction_status(client, ids, transaction_id, "APPROVED", token_key="admin_token")
    assert response.status_code == 200, response.text


def test_completed_transfer_appends_ownership_history(client):
    ids = _setup_data()
    transaction_id = _create_transaction_for_completion(client, ids)
    _approve_transaction(client, ids, transaction_id)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED", token_key="admin_token"
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
        assert rows[0].reason_type == "SALE"
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
    transaction_id = _create_transaction_for_completion(client, ids)
    _record_initial_owner(ids, owner_id=ids["buyer_id"])
    _approve_transaction(client, ids, transaction_id)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED", token_key="admin_token"
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
            == 2
        )
    finally:
        db.close()


def test_completed_transfer_requires_established_ownership(client):
    ids = _setup_data(include_initial_ownership=False)
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
    assert response.status_code == 409
    assert "no valid current registered owner" in response.json()["detail"].lower()

    db = TestingSessionLocal()
    try:
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
    transaction_id = _create_transaction_for_completion(client, ids)

    response = _set_transaction_status(
        client, ids, transaction_id, "COMPLETED", token_key="admin_token"
    )
    assert response.status_code == 400

    db = TestingSessionLocal()
    try:
        from app.models.transaction import Transaction

        transaction = db.query(Transaction).filter_by(id=transaction_id).one()
        assert transaction.status == "PENDING_REVIEW"
        assert (
            db.query(OwnershipHistory)
            .filter_by(parcel_id=ids["parcel_id"])
            .count()
            == 1
        )
    finally:
        db.close()


def test_delete_transaction(client):
    ids = _setup_data()
    db = TestingSessionLocal()
    transaction = Transaction(
        transaction_code="TX-DISPOSABLE-001",
        parcel_id=ids["parcel_id"],
        seller_owner_id=ids["seller_id"],
        buyer_owner_id=ids["buyer_id"],
        transaction_type="SALE",
        transaction_date=datetime.utcnow(),
        is_disposable=True,
    )
    db.add(transaction)
    db.commit()
    transaction_id = transaction.id
    db.close()

    headers = {"Authorization": f"Bearer {ids['admin_token']}"}
    response = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers=headers,
        json={"reason": "Disposable test cleanup"},
    )
    assert response.status_code == 204

    # Verify transaction is gone
    get_res = client.get(f"/api/transactions/{transaction_id}", headers=headers)
    assert get_res.status_code == 404

    # Non-existent deletion returns 404
    del_404 = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers=headers,
        json={"reason": "Disposable test cleanup"},
    )
    assert del_404.status_code == 404


def _create_disposable_transaction(ids, with_risk=False):
    db = TestingSessionLocal()
    transaction = Transaction(
        transaction_code="TX-DISPOSABLE-002",
        parcel_id=ids["parcel_id"],
        seller_owner_id=ids["seller_id"],
        buyer_owner_id=ids["buyer_id"],
        transaction_type="SALE",
        transaction_date=datetime.utcnow(),
        is_disposable=True,
    )
    db.add(transaction)
    db.flush()
    if with_risk:
        db.add(RiskPrediction(
            transaction_id=transaction.id,
            risk_score=15,
            risk_level="LOW",
            model_version="test",
        ))
    db.commit()
    transaction_id = transaction.id
    db.close()
    return transaction_id


def test_admin_deletes_disposable_transaction_with_predictions(client):
    ids = _setup_data()
    transaction_id = _create_disposable_transaction(ids, with_risk=True)

    response = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={"reason": "Remove isolated disposable test transaction"},
    )
    assert response.status_code == 204

    db = TestingSessionLocal()
    try:
        assert db.query(Transaction).filter_by(id=transaction_id).one_or_none() is None
        assert db.query(RiskPrediction).filter_by(transaction_id=transaction_id).count() == 0
    finally:
        db.close()


def test_admin_cannot_delete_genuine_transaction(client):
    ids = _setup_data()
    db = TestingSessionLocal()
    transaction = Transaction(
        transaction_code="TX-GENUINE-001",
        parcel_id=ids["parcel_id"],
        transaction_type="SALE",
        transaction_date=datetime.utcnow(),
        status="COMPLETED",
    )
    db.add(transaction)
    db.commit()
    transaction_id = transaction.id
    db.close()

    response = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={"reason": "Attempted removal of protected completed record"},
    )
    assert response.status_code == 409
    assert "archive" in response.json()["detail"].lower()


@pytest.mark.parametrize("token_key", ["token", "auditor_token"])
def test_non_admin_cannot_delete_transaction(client, token_key):
    ids = _setup_data()
    transaction_id = _create_disposable_transaction(ids)
    response = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers={"Authorization": f"Bearer {ids[token_key]}"},
        json={"reason": "Unauthorized deletion attempt"},
    )
    assert response.status_code == 403


def test_archive_preserves_transaction_and_predictions(client):
    ids = _setup_data()
    transaction_id = _create_disposable_transaction(ids, with_risk=True)

    response = client.post(
        f"/api/transactions/{transaction_id}/archive",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["is_archived"] is True

    db = TestingSessionLocal()
    try:
        assert db.query(Transaction).filter_by(id=transaction_id).one().is_archived is True
        assert db.query(RiskPrediction).filter_by(transaction_id=transaction_id).count() == 1
    finally:
        db.close()


def test_missing_transaction_delete_returns_404(client):
    ids = _setup_data()
    response = client.request(
        "DELETE",
        "/api/transactions/99999",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={"reason": "Missing transaction test"},
    )
    assert response.status_code == 404


def test_failed_delete_rolls_back_transaction_and_dependencies(client, monkeypatch):
    ids = _setup_data()
    transaction_id = _create_disposable_transaction(ids, with_risk=True)

    def fail_audit(*args, **kwargs):
        from sqlalchemy.exc import SQLAlchemyError

        raise SQLAlchemyError("audit failure")

    monkeypatch.setattr(transaction_routes, "record_audit", fail_audit)
    response = client.request(
        "DELETE",
        f"/api/transactions/{transaction_id}",
        headers={"Authorization": f"Bearer {ids['admin_token']}"},
        json={"reason": "Rollback test"},
    )
    assert response.status_code == 500

    db = TestingSessionLocal()
    try:
        assert db.query(Transaction).filter_by(id=transaction_id).one_or_none() is not None
        assert db.query(RiskPrediction).filter_by(transaction_id=transaction_id).count() == 1
    finally:
        db.close()
