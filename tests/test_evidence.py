"""Tests for transaction evidence management."""
from __future__ import annotations

import io
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
from app.models.owner import Owner
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


def _setup_data():
    db = TestingSessionLocal()
    officer_role = Role(name="OFFICER", description="Officer")
    auditor_role = Role(name="AUDITOR", description="Auditor")
    db.add_all([officer_role, auditor_role])
    db.flush()
    user = User(
        username="evidence-officer",
        full_name="Evidence Officer",
        email="evidence-officer@test.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=True,
        roles=[officer_role],
    )
    auditor = User(
        username="evidence-auditor",
        full_name="Evidence Auditor",
        email="evidence-auditor@test.local",
        password_hash=hash_password("AuditorPass123!"),
        is_active=True,
        roles=[auditor_role],
    )
    db.add_all([user, auditor])
    db.flush()

    seller = Owner(owner_code="OWN-EVID-001", full_name="Seller", status="ACTIVE")
    buyer = Owner(owner_code="OWN-EVID-002", full_name="Buyer", status="ACTIVE")
    parcel = Parcel(
        upi="UPI-EVID-001",
        parcel_code="RW-EVID-001",
        location="Test Location",
        province="Kigali",
        district="Gasabo",
        sector="Kacyiru",
        cell="Cell",
        village="Village",
        area_ha=1.0,
        status="ACTIVE",
    )
    db.add_all([seller, buyer, parcel])
    db.flush()

    tx = Transaction(
        transaction_code="TX-EVID-001",
        parcel_id=parcel.id,
        seller_owner_id=seller.id,
        buyer_owner_id=buyer.id,
        transaction_type="SALE",
        status="PENDING",
        created_by=user.id,
    )
    db.add(tx)
    db.commit()
    token = create_auth_token(user, role="OFFICER")
    auditor_token = create_auth_token(auditor, role="AUDITOR")
    ids = {"token": token, "auditor_token": auditor_token, "tx_id": tx.id, "user_id": user.id}
    db.close()
    return ids


def test_upload_evidence_success(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    pdf_content = b"%PDF-1.4 test content"
    response = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT", "stated_payment_amount": "15000000", "payment_reference": "PAY-001"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == "SALE_AGREEMENT"
    assert data["status"] == "UPLOADED"
    assert data["original_filename"] == "test.pdf"
    assert data["file_size"] == len(pdf_content)


def test_upload_evidence_rejects_invalid_file_type(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    response = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert response.status_code == 400


def test_upload_evidence_rejects_oversized_file(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    large_content = b"x" * (11 * 1024 * 1024)  # 11 MB
    response = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert response.status_code == 400


def test_upload_evidence_nonexistent_transaction(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    response = client.post(
        "/api/evidence/transactions/99999",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert response.status_code == 404


def test_upload_evidence_unauthenticated(client):
    ids = _setup_data()
    response = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert response.status_code == 401


def test_list_transaction_evidence(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    response = client.get(f"/api/evidence/transactions/{ids['tx_id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["document_type"] == "SALE_AGREEMENT"


def test_review_evidence_status_transition(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    upload_resp = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    evidence_id = upload_resp.json()["id"]
    response = client.put(
        f"/api/evidence/{evidence_id}/review",
        headers=headers,
        json={"status": "VERIFIED_FOR_REVIEW", "review_notes": "Document verified"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "VERIFIED_FOR_REVIEW"
    assert response.json()["review_notes"] == "Document verified"


def test_review_history_preserved(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    upload_resp = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    evidence_id = upload_resp.json()["id"]
    client.put(f"/api/evidence/{evidence_id}/review", headers=headers, json={"status": "UNDER_REVIEW", "review_notes": "Reviewing"})
    client.put(f"/api/evidence/{evidence_id}/review", headers=headers, json={"status": "VERIFIED_FOR_REVIEW", "review_notes": "Verified"})
    response = client.get(f"/api/evidence/{evidence_id}/review-history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3  # upload + 2 reviews


def test_evidence_does_not_complete_transaction(client):
    ids = _setup_data()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "PAYMENT_RECEIPT"},
    )
    client.put(f"/api/evidence/1/review", headers=headers, json={"status": "VERIFIED_FOR_REVIEW", "review_notes": "Verified"})
    tx_resp = client.get(f"/api/transactions/{ids['tx_id']}", headers=headers)
    assert tx_resp.json()["status"] == "PENDING"


def test_auditor_can_view_evidence(client):
    ids = _setup_data()
    officer_headers = {"Authorization": f"Bearer {ids['token']}"}
    auditor_headers = {"Authorization": f"Bearer {ids['auditor_token']}"}
    upload_resp = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=officer_headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]
    list_resp = client.get(f"/api/evidence/transactions/{ids['tx_id']}", headers=auditor_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    download_resp = client.get(f"/api/evidence/{evidence_id}", headers=auditor_headers)
    assert download_resp.status_code == 200
    upload_resp2 = client.post(
        f"/api/evidence/transactions/{ids['tx_id']}",
        headers=auditor_headers,
        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        data={"document_type": "SALE_AGREEMENT"},
    )
    assert upload_resp2.status_code == 403
