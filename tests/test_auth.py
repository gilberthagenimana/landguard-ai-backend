"""Tests for authentication endpoints and JWT security."""
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


def _create_user(username, email, password, role_name):
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
    db.close()


def test_login_success(client):
    _create_user("officer1", "officer@test.local", "OfficerPass123!", "OFFICER")
    response = client.post(
        "/api/auth/login",
        json={"email": "officer@test.local", "password": "OfficerPass123!", "role": "OFFICER"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_with_username(client):
    _create_user("admin1", "admin@test.local", "AdminPass123!", "ADMIN")
    response = client.post(
        "/api/auth/login",
        json={"username": "admin1", "password": "AdminPass123!", "role": "ADMIN"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_password(client):
    _create_user("officer2", "officer2@test.local", "OfficerPass123!", "OFFICER")
    response = client.post(
        "/api/auth/login",
        json={"email": "officer2@test.local", "password": "WrongPassword!", "role": "OFFICER"},
    )
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@test.local", "password": "SomePass123!", "role": "OFFICER"},
    )
    assert response.status_code == 401


def test_login_wrong_role(client):
    _create_user("officer3", "officer3@test.local", "OfficerPass123!", "OFFICER")
    response = client.post(
        "/api/auth/login",
        json={"email": "officer3@test.local", "password": "OfficerPass123!", "role": "ADMIN"},
    )
    assert response.status_code == 403


def test_get_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_get_me_success(client):
    _create_user("officer4", "officer4@test.local", "OfficerPass123!", "OFFICER")
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "officer4@test.local", "password": "OfficerPass123!", "role": "OFFICER"},
    )
    token = login_resp.json()["access_token"]
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "officer4@test.local"
    assert "OFFICER" in data["roles"]


def test_logout_success(client):
    _create_user("officer5", "officer5@test.local", "OfficerPass123!", "OFFICER")
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "officer5@test.local", "password": "OfficerPass123!", "role": "OFFICER"},
    )
    token = login_resp.json()["access_token"]
    response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Signed out"


def test_inactive_user_cannot_login(client):
    db = TestingSessionLocal()
    role = Role(name="OFFICER", description="Officer")
    db.add(role)
    db.flush()
    user = User(
        username="inactive1",
        full_name="Inactive User",
        email="inactive@test.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=False,
        roles=[role],
    )
    db.add(user)
    db.commit()
    db.close()

    response = client.post(
        "/api/auth/login",
        json={"email": "inactive@test.local", "password": "OfficerPass123!", "role": "OFFICER"},
    )
    assert response.status_code == 401


def test_invalid_token_rejected(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token-here"},
    )
    assert response.status_code == 401
