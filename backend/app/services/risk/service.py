from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import log
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.transaction_status import TransactionStatus
from app.models.ownership_history import OwnershipHistory
from app.models.risk_prediction import RiskPrediction
from app.models.transaction import Transaction
from app.schemas.risk import RiskAnalysisResponse

RISK_FEATURES = [
    "seller_owner_match",
    "duplicate_transaction",
    "recent_ownership_change",
    "record_inconsistency",
    "ownership_changes",
    "previous_transactions",
    "transaction_frequency_30d",
    "days_since_previous_transaction",
    "transaction_value_log",
]

ACTIVE_TRANSACTION_STATUSES = (
    TransactionStatus.PENDING.value,
    TransactionStatus.UNDER_REVIEW.value,
    TransactionStatus.FLAGGED.value,
)

FEATURE_DESCRIPTIONS = {
    "seller_owner_match": "Seller matches the latest recorded owner",
    "duplicate_transaction": "Another active transaction exists for this parcel",
    "recent_ownership_change": "Ownership changed within the last 30 days",
    "record_inconsistency": "Transaction information is incomplete or inconsistent",
    "ownership_changes": "Number of recorded ownership changes",
    "previous_transactions": "Number of previous transactions for this parcel",
    "transaction_frequency_30d": "Transactions recorded in the last 30 days",
    "days_since_previous_transaction": "Days since the previous transaction",
    "transaction_value_log": "Logarithm of the declared transaction value",
}


class RiskModelUnavailable(Exception):
    """Raised when the trained model artifact is unavailable."""


def _model_path() -> Path:
    configured = Path(settings.model_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[4] / configured


def build_transaction_features(
    db: Session,
    transaction: Transaction,
) -> dict:
    recent_cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(days=30)
    )

    ownership_changes = (
        db.query(OwnershipHistory)
        .filter(OwnershipHistory.parcel_id == transaction.parcel_id)
        .all()
    )

    previous_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.parcel_id == transaction.parcel_id,
            Transaction.id != transaction.id,
        )
        .all()
    )

    recent_transactions = [
        item
        for item in previous_transactions
        if item.transaction_date >= recent_cutoff
    ]

    latest_owner = max(
        ownership_changes,
        key=lambda item: item.transfer_date,
        default=None,
    )

    active_conflict = next(
        (
            item
            for item in previous_transactions
            if item.status in ACTIVE_TRANSACTION_STATUSES
        ),
        None,
    )

    previous_dates = [
        item.transaction_date for item in previous_transactions
    ]

    days_since = 1500
    if previous_dates:
        days_since = min(
            (
                transaction.transaction_date - max(previous_dates)
            ).days,
            1500,
        )
        days_since = max(days_since, 0)

    declared = float(transaction.declared_value or 1)

    return {
        "seller_owner_match": int(
            bool(
                latest_owner
                and transaction.seller_owner_id == latest_owner.new_owner_id
            )
        ),
        "duplicate_transaction": int(active_conflict is not None),
        "recent_ownership_change": int(
            any(
                item.transfer_date >= recent_cutoff
                for item in ownership_changes
            )
        ),
        "record_inconsistency": int(
            transaction.seller_owner_id is None
            or transaction.parcel_id is None
            or transaction.buyer_owner_id is None
        ),
        "ownership_changes": len(ownership_changes),
        "previous_transactions": len(previous_transactions),
        "transaction_frequency_30d": len(recent_transactions),
        "days_since_previous_transaction": days_since,
        "transaction_value_log": round(log(max(declared, 1.0)), 4),
    }


def get_feature_importance(features: dict) -> list[dict]:
    """Return rule-based review indicators; not model feature importance."""
    indicators = []

    rules = {
        "seller_owner_match": (
            lambda value: value == 0,
            "HIGH",
        ),
        "duplicate_transaction": (
            lambda value: value == 1,
            "HIGH",
        ),
        "recent_ownership_change": (
            lambda value: value == 1,
            "MEDIUM",
        ),
        "record_inconsistency": (
            lambda value: value == 1,
            "HIGH",
        ),
        "transaction_frequency_30d": (
            lambda value: value > 2,
            "MEDIUM",
        ),
        "days_since_previous_transaction": (
            lambda value: value < 30,
            "MEDIUM",
        ),
    }

    for name, (condition, impact) in rules.items():
        if condition(features.get(name)):
            indicators.append(
                {
                    "feature": name,
                    "description": FEATURE_DESCRIPTIONS[name],
                    "impact": impact,
                }
            )

    return indicators


def analyze_transaction(
    db: Session,
    transaction: Transaction,
) -> RiskAnalysisResponse:
    model_path = _model_path()
    if not model_path.exists():
        raise RiskModelUnavailable

    model = joblib.load(model_path)
    features = build_transaction_features(db, transaction)

    frame = pd.DataFrame(
        [{name: features[name] for name in RISK_FEATURES}]
    )

    risk_level = str(model.predict(frame)[0])
    probabilities = model.predict_proba(frame)[0]

    score_weights = {
        "LOW": 20,
        "MEDIUM": 55,
        "HIGH": 85,
    }
    risk_score = round(
        sum(
            float(probability) * score_weights[str(label)]
            for label, probability in zip(model.classes_, probabilities)
        )
    )

    reasons: list[str] = []
    if features["duplicate_transaction"]:
        reasons.append(
            "Another active transaction exists for this parcel; review for a possible conflict."
        )
    if features["seller_owner_match"] == 0:
        reasons.append(
            "The seller does not match the latest recorded owner; verify the ownership records."
        )
    if features["recent_ownership_change"]:
        reasons.append(
            "A recent ownership change was detected; verify the supporting records."
        )
    if features["transaction_frequency_30d"] > 2:
        reasons.append(
            "Several transactions were recorded within 30 days; review the transaction history."
        )
    if features["record_inconsistency"]:
        reasons.append(
            "Transaction information is incomplete or inconsistent."
        )
    if features["days_since_previous_transaction"] < 30:
        reasons.append(
            "This transaction follows a previous transaction within 30 days."
        )
    if not reasons:
        reasons.append(
            "No elevated rule-based risk indicators were observed in the available records."
        )

    record = RiskPrediction(
        transaction_id=transaction.id,
        risk_score=risk_score,
        risk_level=risk_level,
        model_version="random_forest-v2-synthetic",
        explanation=" ".join(reasons),
        indicators=reasons,
    )

    db.add(record)
    db.flush()

    return RiskAnalysisResponse(
        transaction_id=transaction.id,
        risk_score=risk_score,
        risk_level=risk_level,
        model_version=record.model_version,
        reasons=reasons,
        analyzed_at=datetime.now(timezone.utc),
    )


def batch_analyze_transactions(
    db: Session,
    transaction_ids: list[int],
) -> list[RiskAnalysisResponse]:
    """Analyze existing transactions; missing model artifacts are skipped."""
    results = []
    for transaction_id in transaction_ids:
        transaction = (
            db.query(Transaction)
            .filter(Transaction.id == transaction_id)
            .first()
        )
        if transaction is None:
            continue
        try:
            results.append(analyze_transaction(db, transaction))
        except RiskModelUnavailable:
            continue
    return results
