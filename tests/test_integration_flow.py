from datetime import datetime
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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

import pytest

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSession()
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


client = TestClient(app)


def _setup():
    db = TestingSession()
    officer_role = db.query(Role).filter(Role.name == "OFFICER").first() or Role(name="OFFICER")
    officer = User(
        username="int-officer",
        full_name="Officer",
        email="int-officer@example.com",
        password_hash=hash_password("Pass12345"),
        is_active=True,
        roles=[officer_role],
    )
    owner = Owner(owner_code="OWN-INT", full_name="Owner One", status="ACTIVE")
    buyer = Owner(owner_code="OWN-BUY", full_name="Buyer One", status="ACTIVE")
    parcel = Parcel(
        parcel_code="RW-INT-001",
        location="Kigali",
        province="Kigali",
        district="Gasabo",
        sector="Kacyiru",
        cell="A",
        village="Demo",
        area_ha=1.2,
        status="ACTIVE",
    )
    db.add_all([officer, owner, buyer, parcel])
    db.flush()
    db.add(OwnershipHistory(parcel_id=parcel.id, new_owner_id=owner.id, transfer_date=datetime.utcnow()))
    db.commit()
    token = create_auth_token(officer)
    ids = {"token": token, "parcel_id": parcel.id, "seller_id": owner.id, "buyer_id": buyer.id}
    db.close()
    return ids


def test_parcel_transaction_verification_flow():
    ids = _setup()
    headers = {"Authorization": f"Bearer {ids['token']}"}
    created = client.post(
        "/api/transactions",
        headers=headers,
        json={
            "parcel_id": ids["parcel_id"],
            "seller_owner_id": ids["seller_id"],
            "buyer_owner_id": ids["buyer_id"],
            "transaction_type": "SALE",
            "transaction_date": datetime.utcnow().isoformat(),
            "declared_value": "1000000",
            "status": "PENDING",
        },
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]
    verified = client.post(f"/api/verification/transactions/{transaction_id}", headers=headers)
    assert verified.status_code == 200
    assert "results" in verified.json()
    logs = client.get("/api/audit-logs", headers=headers)
    assert logs.status_code == 403
