"""Tests for audit logging."""
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


def _get_admin_token():
    db = TestingSessionLocal()
    role = Role(name="ADMIN", description="Admin")
    db.add(role)
    db.flush()
    user = User(
        username="audit-admin", full_name="Audit Admin", email="audit-admin@test.local",
        password_hash=hash_password("AdminPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    return token


def test_audit_logs_accessible_by_admin(client):
    token = _get_admin_token()
    response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_audit_logs_accessible_by_auditor(client):
    db = TestingSessionLocal()
    role = Role(name="AUDITOR", description="Auditor")
    db.add(role)
    db.flush()
    user = User(
        username="audit-auditor", full_name="Audit Auditor", email="audit-auditor@test.local",
        password_hash=hash_password("AuditorPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_audit_logs_not_accessible_by_officer(client):
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="audit-officer", full_name="Audit Officer", email="audit-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_audit_logs_search(client):
    token = _get_admin_token()
    response = client.get("/api/audit-logs?q=LOGIN", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_audit_logs_limited_to_200(client):
    token = _get_admin_token()
    response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) <= 200
