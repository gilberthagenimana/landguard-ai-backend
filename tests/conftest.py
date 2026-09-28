"""Shared pytest fixtures for LandGuard AI test suite.

Note: The setup_db fixture is NOT autouse. Each test file manages its own
database engine and setup. This conftest provides optional shared fixtures.
"""
from __future__ import annotations

from datetime import datetime, timedelta
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
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.role import Role
from app.models.transaction import Transaction
from app.models.user import User
from app.services.auth.service import create_auth_token

# Shared in-memory test database
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """FastAPI TestClient with fresh database."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide direct database session for service-level tests."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_officer_token(db=None):
    """Helper to create an officer user and return JWT token."""
    close_after = False
    if db is None:
        db = TestingSessionLocal()
        close_after = True
    role = db.query(Role).filter(Role.name == "OFFICER").first()
    if not role:
        role = Role(name="OFFICER", description="Verification Officer")
        db.add(role)
        db.flush()
    user = User(
        username="test-officer",
        full_name="Test Officer",
        email="test-officer@test.local",
        password_hash=hash_password("OfficerPass123!"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    if close_after:
        db.close()
    return token


def make_admin_token(db=None):
    """Helper to create an admin user and return JWT token."""
    close_after = False
    if db is None:
        db = TestingSessionLocal()
        close_after = True
    role = db.query(Role).filter(Role.name == "ADMIN").first()
    if not role:
        role = Role(name="ADMIN", description="Administrator")
        db.add(role)
        db.flush()
    user = User(
        username="test-admin",
        full_name="Test Admin",
        email="test-admin@test.local",
        password_hash=hash_password("AdminPass123!"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    if close_after:
        db.close()
    return token


def make_auditor_token(db=None):
    """Helper to create an auditor user and return JWT token."""
    close_after = False
    if db is None:
        db = TestingSessionLocal()
        close_after = True
    role = db.query(Role).filter(Role.name == "AUDITOR").first()
    if not role:
        role = Role(name="AUDITOR", description="Auditor")
        db.add(role)
        db.flush()
    user = User(
        username="test-auditor",
        full_name="Test Auditor",
        email="test-auditor@test.local",
        password_hash=hash_password("AuditorPass123!"),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    token = create_auth_token(user)
    if close_after:
        db.close()
    return token


def create_test_parcel(db, **kwargs):
    """Create a test parcel with sensible defaults."""
    defaults = {
        "parcel_code": "RW-TEST-001",
        "location": "Kigali / Test Sector / Test Cell",
        "province": "Kigali",
        "district": "Gasabo",
        "sector": "Kacyiru",
        "cell": "Test Cell",
        "village": "Test Village",
        "area_ha": 1.5,
        "status": "ACTIVE",
    }
    defaults.update(kwargs)
    parcel = Parcel(**defaults)
    db.add(parcel)
    db.commit()
    db.refresh(parcel)
    return parcel


def create_test_owner(db, **kwargs):
    """Create a test owner with sensible defaults."""
    defaults = {
        "owner_code": "OWN-TEST-001",
        "full_name": "Test Owner",
        "identification_number": "11995521-DEMO",
        "phone": "+250780000001",
        "email": "owner@test.local",
        "status": "ACTIVE",
    }
    defaults.update(kwargs)
    owner = Owner(**defaults)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def create_test_transaction(db, parcel_id, seller_id, buyer_id, **kwargs):
    """Create a test transaction with sensible defaults."""
    defaults = {
        "transaction_code": "TX-TEST-001",
        "parcel_id": parcel_id,
        "seller_owner_id": seller_id,
        "buyer_owner_id": buyer_id,
        "transaction_type": "SALE",
        "transaction_date": datetime.utcnow(),
        "declared_value": 1000000,
        "status": "PENDING",
    }
    defaults.update(kwargs)
    transaction = Transaction(**defaults)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def create_ownership_history(db, parcel_id, new_owner_id, **kwargs):
    """Create an ownership history record."""
    defaults = {
        "parcel_id": parcel_id,
        "new_owner_id": new_owner_id,
        "transfer_date": datetime.utcnow() - timedelta(days=365),
        "reason_type": "FIRST_REGISTRATION",
    }
    defaults.update(kwargs)
    history = OwnershipHistory(**defaults)
    db.add(history)
    db.commit()
    db.refresh(history)
    return history
