from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from ml.training.train import FEATURES


REASONS = {
    "seller_owner_match": "Seller does not match the latest recorded owner.",
    "duplicate_transaction": "Possible duplicate or conflicting transaction detected.",
    "recent_ownership_change": "Recent ownership change detected.",
    "record_inconsistency": "Inconsistent transaction information detected.",
    "transaction_frequency_30d": "Unusual transaction frequency detected.",
}


def predict_risk(features: dict, model_path: Path = Path("ml/models/risk_model.joblib")) -> dict:
    missing = set(FEATURES) - set(features)
    if missing:
        raise ValueError(f"Missing risk features: {sorted(missing)}")
    model = joblib.load(model_path)
    frame = pd.DataFrame([{name: features[name] for name in FEATURES}])
    level = str(model.predict(frame)[0])
    probabilities = model.predict_proba(frame)[0]
    classes = list(model.classes_)
    score = round(sum(float(probability) * {"LOW": 20, "MEDIUM": 55, "HIGH": 85}[label] for label, probability in zip(classes, probabilities)))
    reasons = [REASONS[name] for name in REASONS if features.get(name) and name in features]
    return {"risk_score": score, "risk_level": level, "reasons": reasons}
