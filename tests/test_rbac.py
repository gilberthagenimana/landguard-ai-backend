"""Tests for Role-Based Access Control enforcement."""
from __future__ import annotations

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


def _create_user_with_role(username, email, password, role_name):
    db = TestingSessionLocal()
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.flush()
    user = User(
        username=username,
        full_name=f"{role_name} User",
        email=email,
        password_hash=hash_password(password),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_officer_cannot_access_users_list(client):
    user = _create_user_with_role("rbac-officer", "rbac-officer@test.local", "OfficerPass123!", "OFFICER")
    token = create_auth_token(user)
    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_auditor_cannot_access_users_list(client):
    user = _create_user_with_role("rbac-auditor", "rbac-auditor@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_access_users_list(client):
    user = _create_user_with_role("rbac-admin", "rbac-admin@test.local", "AdminPass123!", "ADMIN")
    token = create_auth_token(user)
    response = client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_officer_cannot_create_user(client):
    user = _create_user_with_role("rbac-officer2", "rbac-officer2@test.local", "OfficerPass123!", "OFFICER")
    token = create_auth_token(user)
    response = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "New User",
            "email": "new@test.local",
            "password": "Password123!",
            "role": "OFFICER",
        },
    )
    assert response.status_code == 403


def test_auditor_can_access_audit_logs(client):
    user = _create_user_with_role("rbac-auditor2", "rbac-auditor2@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.get(
        "/api/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_officer_cannot_access_audit_logs(client):
    user = _create_user_with_role("rbac-officer3", "rbac-officer3@test.local", "OfficerPass123!", "OFFICER")
    token = create_auth_token(user)
    response = client.get(
        "/api/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_access_audit_logs(client):
    user = _create_user_with_role("rbac-admin2", "rbac-admin2@test.local", "AdminPass123!", "ADMIN")
    token = create_auth_token(user)
    response = client.get(
        "/api/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_unauthenticated_request_rejected(client):
    response = client.get("/api/parcels")
    assert response.status_code == 401


def test_auditor_can_view_parcels(client):
    user = _create_user_with_role("rbac-auditor3", "rbac-auditor3@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.get(
        "/api/parcels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_auditor_cannot_create_parcel(client):
    user = _create_user_with_role("rbac-auditor4", "rbac-auditor4@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.post(
        "/api/parcels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parcel_code": "RW-RBAC-001",
            "location": "Test Location",
            "province": "Kigali",
            "district": "Gasabo",
            "sector": "Kacyiru",
            "cell": "Cell",
            "village": "Village",
            "area_ha": 1.0,
        },
    )
    assert response.status_code == 403


def test_auditor_cannot_run_verification(client):
    user = _create_user_with_role("rbac-auditor5", "rbac-auditor5@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.post(
        "/api/verification/transactions/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_auditor_cannot_run_risk_analysis(client):
    user = _create_user_with_role("rbac-auditor6", "rbac-auditor6@test.local", "AuditorPass123!", "AUDITOR")
    token = create_auth_token(user)
    response = client.post(
        "/api/risk-analysis/transactions/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
