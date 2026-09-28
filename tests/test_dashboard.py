"""Tests for dashboard statistics endpoint."""
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


def _get_officer_token():
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="dash-officer", full_name="Dash Officer", email="dash-officer@test.local",
        password_hash=hash_password("OfficerPass123!"), is_active=True, roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    return token


def test_dashboard_stats_accessible(client):
    token = _get_officer_token()
    response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "total_parcels" in data
    assert "total_owners" in data
    assert "total_transactions" in data
    assert "transactions_under_review" in data
    assert "low_risk_transactions" in data
    assert "medium_risk_transactions" in data
    assert "high_risk_transactions" in data
    assert "recent_verification_activity" in data
    assert "recent_alerts" in data
    assert "viewer_role" in data


def test_dashboard_stats_all_roles(client):
    db = TestingSessionLocal()
    for role_name in ["ADMIN", "OFFICER", "AUDITOR"]:
        role = Role(name=role_name, description=role_name)
        db.add(role)
        db.flush()
        user = User(
            username=f"dash-{role_name.lower()}", full_name=f"Dash {role_name}",
            email=f"dash-{role_name.lower()}@test.local", password_hash=hash_password("Password123!"),
            is_active=True, roles=[role],
        )
        db.add(user)
        db.commit()
    db.close()
    db = TestingSessionLocal()
    for role_name in ["ADMIN", "OFFICER", "AUDITOR"]:
        user = db.query(User).filter(User.username == f"dash-{role_name.lower()}").first()
        token = create_auth_token(user)
        response = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, f"Failed for role {role_name}"
    db.close()


def test_dashboard_stats_requires_auth(client):
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 401
