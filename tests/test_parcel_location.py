from datetime import datetime
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.user import User
from app.services.auth.service import create_auth_token

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine)


def override_get_db():
    db = Session()
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


def _user(role_name: str, email: str) -> str:
    db = Session()
    role = Role(name=role_name, description=role_name)
    user = User(
        username=email.split("@")[0],
        full_name=f"{role_name} User",
        email=email,
        password_hash=hash_password("Pass12345"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user, role_name)
    db.close()
    return token


def _parcel() -> int:
    db = Session()
    parcel = Parcel(
        upi="UPI-LOCATION-001",
        parcel_code="RW-LOCATION-001",
        location="Kigali / Gasabo / Kacyiru",
        province="Kigali",
        district="Gasabo",
        sector="Kacyiru",
        cell="A",
        village="Test",
        area_ha=1.2,
        status="ACTIVE",
    )
    db.add(parcel)
    db.commit()
    parcel_id = parcel.id
    db.close()
    return parcel_id


def test_missing_location_remains_searchable_and_unverified():
    parcel_id = _parcel()
    token = _user("OFFICER", "location-officer@test.local")
    response = TestClient(app).get("/api/parcels/upi/UPI-LOCATION-001", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == parcel_id
    assert response.json()["location_verification_status"] == "NOT_SUBMITTED"
    assert response.json()["latitude"] is None


def test_officer_submission_is_pending_and_audited():
    parcel_id = _parcel()
    token = _user("OFFICER", "submit-officer@test.local")
    response = TestClient(app).post(
        f"/api/parcels/{parcel_id}/location-submissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"latitude": -1.9441, "longitude": 30.0619, "source": "Authorized cadastral survey", "metadata": {"reference": "AUTH-001"}},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING_VERIFICATION"
    assert response.json()["source"] == "Authorized cadastral survey"


def test_admin_verification_promotes_location_without_overwriting_submission():
    parcel_id = _parcel()
    officer = _user("OFFICER", "promote-officer@test.local")
    admin = _user("ADMIN", "promote-admin@test.local")
    client = TestClient(app)
    submitted = client.post(
        f"/api/parcels/{parcel_id}/location-submissions",
        headers={"Authorization": f"Bearer {officer}"},
        json={"latitude": -1.9441, "longitude": 30.0619, "source": "Authorized cadastral survey"},
    )
    submission_id = submitted.json()["id"]
    reviewed = client.put(
        f"/api/parcels/location-submissions/{submission_id}/review",
        headers={"Authorization": f"Bearer {admin}"},
        json={"decision": "VERIFIED", "review_notes": "Checked against authorized source."},
    )
    assert reviewed.status_code == 200
    parcel = client.get(f"/api/parcels/upi/UPI-LOCATION-001", headers={"Authorization": f"Bearer {admin}"}).json()
    assert parcel["location_verification_status"] == "VERIFIED"
    assert parcel["latitude"] == -1.9441
    assert parcel["longitude"] == 30.0619


def test_auditor_cannot_submit_or_review():
    parcel_id = _parcel()
    auditor = _user("AUDITOR", "location-auditor@test.local")
    client = TestClient(app)
    response = client.post(
        f"/api/parcels/{parcel_id}/location-submissions",
        headers={"Authorization": f"Bearer {auditor}"},
        json={"latitude": -1.9441, "longitude": 30.0619, "source": "Authorized source"},
    )
    assert response.status_code == 403


def test_invalid_location_payloads_are_rejected():
    parcel_id = _parcel()
    officer = _user("OFFICER", "invalid-location@test.local")
    client = TestClient(app)
    invalid_point = client.post(
        f"/api/parcels/{parcel_id}/location-submissions",
        headers={"Authorization": f"Bearer {officer}"},
        json={"latitude": 95, "longitude": 30, "source": "Authorized source"},
    )
    assert invalid_point.status_code == 422
    invalid_geometry = client.post(
        f"/api/parcels/{parcel_id}/location-submissions",
        headers={"Authorization": f"Bearer {officer}"},
        json={"boundary_geometry": {"type": "Polygon", "coordinates": [[[500, 500]]]}, "source": "Authorized source"},
    )
    assert invalid_geometry.status_code == 422
