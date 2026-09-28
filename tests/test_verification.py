from datetime import datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.db.base import Base
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.transaction import Transaction
from app.services.verification.service import verify_transaction

import app.models.audit_log  # noqa: F401, E402
import app.models.case_review  # noqa: F401, E402
import app.models.risk_prediction  # noqa: F401, E402
import app.models.role  # noqa: F401, E402
import app.models.user  # noqa: F401, E402
import app.models.verification_result  # noqa: F401, E402

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_transaction(db, *, recent_change=False, with_conflict=False, seller_matches=True):
    owner = Owner(owner_code="OWN-001", full_name="Registered Owner", status="ACTIVE")
    other_owner = Owner(owner_code="OWN-002", full_name="Other Owner", status="ACTIVE")
    buyer = Owner(owner_code="OWN-003", full_name="Buyer", status="ACTIVE")
    parcel = Parcel(
        parcel_code="RW-TEST-001",
        location="Kigali",
        province="Kigali",
        district="Gasabo",
        sector="Kacyiru",
        cell="A",
        village="Demo",
        area_ha=1.0,
        status="ACTIVE",
    )
    db.add_all([owner, other_owner, buyer, parcel])
    db.flush()

    history = OwnershipHistory(
        parcel_id=parcel.id,
        new_owner_id=owner.id,
        transfer_date=datetime.utcnow() - timedelta(days=5 if recent_change else 90),
    )
    transaction = Transaction(
        transaction_code="TX-TEST-1",
        parcel_id=parcel.id,
        seller_owner_id=owner.id if seller_matches else other_owner.id,
        buyer_owner_id=buyer.id,
        transaction_type="SALE",
        status="PENDING",
        transaction_date=datetime.utcnow(),
    )
    db.add_all([history, transaction])
    db.flush()

    if with_conflict:
        db.add(
            Transaction(
                transaction_code="TX-TEST-2",
                parcel_id=parcel.id,
                seller_owner_id=owner.id,
                buyer_owner_id=other_owner.id,
                transaction_type="SALE",
                status="ACTIVE",
                transaction_date=datetime.utcnow(),
            )
        )
    db.commit()
    return transaction


def test_verification_passes_for_consistent_transaction(db):
    transaction = make_transaction(db)
    results = verify_transaction(db, transaction)
    assert len(results) == 9
    assert all(result.status == "PASS" for result in results)


def test_verification_flags_mismatch_conflict_and_recent_change(db):
    transaction = make_transaction(db, recent_change=True, with_conflict=True, seller_matches=False)
    results = verify_transaction(db, transaction)
    result_by_rule = {result.rule_name: result for result in results}
    assert result_by_rule["Seller ownership match"].status == "FAIL"
    assert result_by_rule["Active transaction already exists"].status == "FAIL"
    assert result_by_rule["Conflicting transaction records"].status == "FAIL"
    assert result_by_rule["Recent ownership change"].status == "WARNING"
