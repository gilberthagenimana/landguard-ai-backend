from datetime import datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))

from app.db.base import Base
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.case_review import CaseReview  # noqa: F401
from app.models.owner import Owner
from app.models.ownership_history import OwnershipHistory
from app.models.parcel import Parcel
from app.models.risk_prediction import RiskPrediction  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.transaction import Transaction
from app.models.user import User  # noqa: F401
from app.models.verification_result import VerificationResultRecord  # noqa: F401
from app.services.risk.service import analyze_transaction

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def test_risk_analysis_returns_explanation_for_transaction():
    db = SessionLocal()
    owner = Owner(owner_code="RISK-OWNER", full_name="Risk Owner", status="ACTIVE")
    parcel = Parcel(
        parcel_code="RW-RISK-001",
        location="Kigali",
        province="Kigali",
        district="Gasabo",
        sector="Kacyiru",
        cell="A",
        village="Demo",
        area_ha=1.0,
        status="ACTIVE",
    )
    db.add_all([owner, parcel])
    db.flush()
    db.add(
        OwnershipHistory(
            parcel_id=parcel.id,
            new_owner_id=owner.id,
            transfer_date=datetime.utcnow() - timedelta(days=5),
        )
    )
    transaction = Transaction(
        transaction_code="TX-RISK-1",
        parcel_id=parcel.id,
        seller_owner_id=owner.id,
        buyer_owner_id=owner.id,
        transaction_type="SALE",
        status="PENDING",
        transaction_date=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()

    result = analyze_transaction(db, transaction)

    assert result.transaction_id == transaction.id
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert 0 <= result.risk_score <= 100
    assert result.model_version
    assert result.reasons
    db.close()
