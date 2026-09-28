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
from app.models.role import Role
from app.models.user import User
from app.services.auth.service import create_auth_token

import pytest

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = SessionLocal()
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


def _admin_token():
    db = SessionLocal()
    admin_role = db.query(Role).filter(Role.name == "ADMIN").first() or Role(name="ADMIN", description="Administrator")
    officer_role = db.query(Role).filter(Role.name == "OFFICER").first() or Role(name="OFFICER", description="Officer")
    auditor_role = db.query(Role).filter(Role.name == "AUDITOR").first() or Role(name="AUDITOR", description="Auditor")
    admin = db.query(User).filter(User.username == "admin-test").first()
    if admin is None:
        admin = User(
            username="admin-test",
            full_name="Admin",
            email="admin@example.com",
            password_hash=hash_password("AdminPass123"),
            is_active=True,
            roles=[admin_role],
        )
        db.add_all([admin, officer_role, auditor_role])
        db.commit()
        db.refresh(admin)
    token = create_auth_token(admin)
    db.close()
    return token


def test_registration_requires_admin():
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Officer User", "email": "officer@example.com", "password": "Pass12345", "role": "OFFICER"},
    )
    assert response.status_code == 401


def test_admin_can_create_officer_with_role():
    token = _admin_token()
    response = client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Officer User", "email": "officer@example.com", "username": "officer1", "password": "Pass12345", "role": "OFFICER"},
    )
    assert response.status_code == 200
    assert response.json()["roles"][0]["name"] == "OFFICER"


def test_officer_cannot_list_users():
    db = SessionLocal()
    officer_role = db.query(Role).filter(Role.name == "OFFICER").first()
    officer = User(
        username="officer-test",
        full_name="Officer",
        email="officer-test@example.com",
        password_hash=hash_password("Pass12345"),
        is_active=True,
        roles=[officer_role],
    )
    db.add(officer)
    db.commit()
    token = create_auth_token(officer)
    db.close()
    response = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
