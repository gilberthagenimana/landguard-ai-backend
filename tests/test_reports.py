"""Tests for report generation endpoints."""
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


def _get_officer_token():
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="report-officer", full_name="Report Officer", email="report-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    return token


def test_verification_report(client):
    token = _get_officer_token()
    response = client.get("/api/reports/verification", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "disclaimer" in data
    assert "items" in data


def test_risk_report(client):
    token = _get_officer_token()
    response = client.get("/api/reports/risk", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "disclaimer" in data
    assert "items" in data


def test_cases_report(client):
    token = _get_officer_token()
    response = client.get("/api/reports/cases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "disclaimer" in data
    assert "items" in data


def test_audit_report(client):
    # Audit report requires ADMIN or AUDITOR role
    db = TestingSessionLocal()
    role = Role(name="ADMIN", description="Admin")
    db.add(role)
    db.flush()
    user = User(
        username="audit-report-admin", full_name="Audit Report Admin", email="audit-report-admin@test.local",
        password_hash=hash_password("AdminPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    response = client.get("/api/reports/audit", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "items" in data


def test_parcel_history_report(client):
    token = _get_officer_token()
    db = TestingSessionLocal()
    owner = Owner(owner_code="OWN-RPT-001", full_name="Report Owner", status="ACTIVE")
    db.add(owner)
    db.flush()
    parcel = Parcel(
        parcel_code="RW-RPT-001", location="Test Location", province="Kigali",
        district="Gasabo", sector="Kacyiru", cell="Cell", village="Village", area_ha=1.0, status="ACTIVE",
    )
    db.add(parcel)
    db.flush()
    history = OwnershipHistory(parcel_id=parcel.id, new_owner_id=owner.id, transfer_date=datetime.utcnow(), reason_type="FIRST_REGISTRATION")
    db.add(history)
    db.commit()
    parcel_id = parcel.id
    db.close()
    response = client.get(f"/api/reports/parcels/{parcel_id}/history", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "title" in data
    assert "parcel_code" in data
    assert "ownership_history" in data
    assert "transactions" in data


def test_parcel_history_report_nonexistent(client):
    token = _get_officer_token()
    response = client.get("/api/reports/parcels/99999/history", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_reports_require_auth(client):
    response = client.get("/api/reports/verification")
    assert response.status_code == 401
