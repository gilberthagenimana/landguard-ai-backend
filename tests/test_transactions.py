"""Tests for transaction CRUD operations."""
from __future__ import annotations

from datetime import datetime
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
        parcel_code="RW-TX-001", location="Test Location", province="Kigali",
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
