"""Tests for owner CRUD operations."""
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
        username="owner-officer",
        full_name="Owner Officer",
        email="owner-officer@test.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    return token


def test_create_owner_success(client):
    token = _get_officer_token()
    response = client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json={
        "owner_code": "OWN-NEW-001", "full_name": "New Owner Person",
        "identification_number": "11995599-DEMO", "phone": "+250780000099",
        "email": "newowner@test.local", "status": "ACTIVE",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["owner_code"] == "OWN-NEW-001"
    assert data["full_name"] == "New Owner Person"
    assert data["parcels_owned"] == 0


def test_create_owner_duplicate_code(client):
    token = _get_officer_token()
    payload = {"owner_code": "OWN-DUP-001", "full_name": "Duplicate Owner", "status": "ACTIVE"}
    response1 = client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response1.status_code == 201
    response2 = client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response2.status_code == 400


def test_list_owners(client):
    token = _get_officer_token()
    client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json={
        "owner_code": "OWN-LIST-001", "full_name": "List Owner", "status": "ACTIVE",
    })
    response = client.get("/api/owners", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_search_owners(client):
    token = _get_officer_token()
    client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json={
        "owner_code": "OWN-SEARCH-001", "full_name": "Searchable Person Name", "status": "ACTIVE",
    })
    response = client.get("/api/owners?q=Searchable", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_owner_by_id(client):
    token = _get_officer_token()
    create_resp = client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json={
        "owner_code": "OWN-GET-001", "full_name": "Get Owner", "status": "ACTIVE",
    })
    owner_id = create_resp.json()["id"]
    response = client.get(f"/api/owners/{owner_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["owner_code"] == "OWN-GET-001"


def test_get_nonexistent_owner(client):
    token = _get_officer_token()
    response = client.get("/api/owners/99999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_update_owner(client):
    token = _get_officer_token()
    create_resp = client.post("/api/owners", headers={"Authorization": f"Bearer {token}"}, json={
        "owner_code": "OWN-UPDATE-001", "full_name": "Original Name", "status": "ACTIVE",
    })
    owner_id = create_resp.json()["id"]
    response = client.put(f"/api/owners/{owner_id}", headers={"Authorization": f"Bearer {token}"}, json={"full_name": "Updated Name", "status": "INACTIVE"})
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["status"] == "INACTIVE"
