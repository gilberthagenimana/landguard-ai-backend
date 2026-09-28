"""Tests for parcel CRUD operations."""
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
        username="parcel-officer",
        full_name="Parcel Officer",
        email="parcel-officer@test.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    db.close()
    return token


def test_create_parcel_success(client):
    token = _get_officer_token()
    response = client.post(
        "/api/parcels",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "parcel_code": "RW-PARCEL-001",
            "location": "Kigali / Test / Cell",
            "province": "Kigali",
            "district": "Gasabo",
            "sector": "Kacyiru",
            "cell": "Test Cell",
            "village": "Test Village",
            "area_ha": 2.5,
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parcel_code"] == "RW-PARCEL-001"
    assert data["area_ha"] == 2.5
    assert data["status"] == "ACTIVE"


def test_create_parcel_duplicate_code(client):
    token = _get_officer_token()
    payload = {
        "parcel_code": "RW-DUPLICATE-001",
        "location": "Test Location",
        "province": "Kigali",
        "district": "Gasabo",
        "sector": "Kacyiru",
        "cell": "Test Cell",
        "village": "Test Village",
        "area_ha": 1.0,
    }
    response1 = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response1.status_code == 201
    response2 = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert response2.status_code == 400


def test_list_parcels(client):
    token = _get_officer_token()
    client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-LIST-001", "location": "Test Location", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Test Cell", "village": "Test Village", "area_ha": 1.0,
    })
    response = client.get("/api/parcels", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["parcel_code"] == "RW-LIST-001" for p in data)


def test_search_parcels(client):
    token = _get_officer_token()
    client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-SEARCH-001", "location": "Kigali / Search / Cell", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Search Cell", "village": "Search Village", "area_ha": 1.0,
    })
    response = client.get("/api/parcels?q=SEARCH", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_parcel_by_id(client):
    token = _get_officer_token()
    create_resp = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-GET-001", "location": "Test Location", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Test Cell", "village": "Test Village", "area_ha": 1.0,
    })
    parcel_id = create_resp.json()["id"]
    response = client.get(f"/api/parcels/{parcel_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["parcel_code"] == "RW-GET-001"


def test_get_nonexistent_parcel(client):
    token = _get_officer_token()
    response = client.get("/api/parcels/99999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_update_parcel(client):
    token = _get_officer_token()
    create_resp = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-UPDATE-001", "location": "Original Location", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Test Cell", "village": "Test Village", "area_ha": 1.0,
    })
    parcel_id = create_resp.json()["id"]
    response = client.put(f"/api/parcels/{parcel_id}", headers={"Authorization": f"Bearer {token}"}, json={"location": "Updated Location", "area_ha": 3.0})
    assert response.status_code == 200
    data = response.json()
    assert data["location"] == "Updated Location"
    assert data["area_ha"] == 3.0


def test_parcel_ownership_history_empty(client):
    token = _get_officer_token()
    create_resp = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-HISTORY-001", "location": "Test Location", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Test Cell", "village": "Test Village", "area_ha": 1.0,
    })
    parcel_id = create_resp.json()["id"]
    response = client.get(f"/api/parcels/{parcel_id}/ownership-history", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


def test_parcel_transactions_empty(client):
    token = _get_officer_token()
    create_resp = client.post("/api/parcels", headers={"Authorization": f"Bearer {token}"}, json={
        "parcel_code": "RW-TX-001", "location": "Test Location", "province": "Kigali",
        "district": "Gasabo", "sector": "Kacyiru", "cell": "Test Cell", "village": "Test Village", "area_ha": 1.0,
    })
    parcel_id = create_resp.json()["id"]
    response = client.get(f"/api/parcels/{parcel_id}/transactions", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []
