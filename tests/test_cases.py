"""Tests for case management workflow."""
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
from app.models.case_review import CaseReview
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.transaction import Transaction
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


def _setup():
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="case-officer", full_name="Case Officer", email="case-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.flush()
    seller = Owner(owner_code="OWN-CASE-001", full_name="Seller", status="ACTIVE")
    buyer = Owner(owner_code="OWN-CASE-002", full_name="Buyer", status="ACTIVE")
    parcel = Parcel(
        parcel_code="RW-CASE-001", location="Test Location", province="Kigali",
        district="Gasabo", sector="Kacyiru", cell="Cell", village="Village", area_ha=1.0, status="ACTIVE",
    )
    db.add_all([seller, buyer, parcel])
    db.flush()
    history = OwnershipHistory(parcel_id=parcel.id, new_owner_id=seller.id, transfer_date=datetime.utcnow(), reason_type="FIRST_REGISTRATION")
    db.add(history)
    db.flush()
    tx = Transaction(
        transaction_code="TX-CASE-001", parcel_id=parcel.id, seller_owner_id=seller.id,
        buyer_owner_id=buyer.id, transaction_type="SALE", transaction_date=datetime.utcnow(),
        declared_value=1000000, status="PENDING",
    )
    db.add(tx)
    db.flush()
    case = CaseReview(case_code="CASE-TEST-001", transaction_id=tx.id, parcel_id=parcel.id, assigned_to=user.id, status="OPEN", review_notes=None)
    db.add(case)
    db.commit()
    token = create_auth_token(user)
    ids = {"token": token, "case_id": case.id, "tx_id": tx.id}
    db.close()
    return ids


def test_list_cases(client):
    ids = _setup()
    response = client.get("/api/cases", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_list_cases_filter_by_status(client):
    ids = _setup()
    response = client.get("/api/cases?status=OPEN", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    data = response.json()
    assert all(c["status"] == "OPEN" for c in data)


def test_get_case_detail(client):
    ids = _setup()
    response = client.get(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 200
    data = response.json()
    assert data["case"]["case_code"] == "CASE-TEST-001"
    assert data["transaction"] is not None
    assert "ownership_history" in data
    assert "verification_results" in data
    assert "disclaimer" in data


def test_get_nonexistent_case(client):
    ids = _setup()
    response = client.get("/api/cases/99999", headers={"Authorization": f"Bearer {ids['token']}"})
    assert response.status_code == 404


def test_update_case_status(client):
    ids = _setup()
    response = client.put(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"}, json={"status": "UNDER_REVIEW", "review_notes": "Reviewing documents"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UNDER_REVIEW"
    assert data["review_notes"] == "Reviewing documents"


def test_update_case_invalid_status(client):
    ids = _setup()
    response = client.put(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"}, json={"status": "INVALID_STATUS"})
    assert response.status_code == 422


def test_update_case_resolved(client):
    ids = _setup()
    response = client.put(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"}, json={"status": "RESOLVED", "review_notes": "All documents verified"})
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


def test_update_case_closed(client):
    ids = _setup()
    response = client.put(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"}, json={"status": "CLOSED", "review_notes": "Case closed with explanation"})
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


def test_update_case_needs_information(client):
    ids = _setup()
    response = client.put(f"/api/cases/{ids['case_id']}", headers={"Authorization": f"Bearer {ids['token']}"}, json={"status": "NEEDS_INFORMATION", "review_notes": "Need certified deed copy"})
    assert response.status_code == 200
    assert response.json()["status"] == "NEEDS_INFORMATION"
