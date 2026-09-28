from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

FEATURES = [
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
TARGET = "risk_level"


def train_models(dataset_path: Path, model_dir: Path, test_size: float = 0.2, seed: int = 42) -> dict:
    dataset = pd.read_csv(dataset_path)
    missing = set(FEATURES + [TARGET]) - set(dataset.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")
    if dataset[TARGET].nunique() < 2:
        raise ValueError("Dataset must contain at least two risk classes")

    x_train, x_test, y_train, y_test = train_test_split(
        dataset[FEATURES], dataset[TARGET], test_size=test_size, random_state=seed, stratify=dataset[TARGET]
    )
    models = {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed)),
            ]
        ),
        "decision_tree": DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=seed),
        "random_forest": RandomForestClassifier(n_estimators=150, max_depth=8, class_weight="balanced", random_state=seed),
    }
    metrics: dict = {}
    trained: dict = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics[name] = {
            "accuracy": round(accuracy_score(y_test, predictions), 4),
            "precision_weighted": round(precision_score(y_test, predictions, average="weighted", zero_division=0), 4),
            "recall_weighted": round(recall_score(y_test, predictions, average="weighted", zero_division=0), 4),
            "f1_weighted": round(f1_score(y_test, predictions, average="weighted", zero_division=0), 4),
            "confusion_matrix": confusion_matrix(y_test, predictions, labels=["LOW", "MEDIUM", "HIGH"]).tolist(),
        }
        trained[name] = model

    selected_name = max(metrics, key=lambda name: metrics[name]["f1_weighted"])
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(trained[selected_name], model_dir / "risk_model.joblib")
    (model_dir / "metrics.json").write_text(
        json.dumps({"selected_model": selected_name, "features": FEATURES, "metrics": metrics}, indent=2),
        encoding="utf-8",
    )
    return {"selected_model": selected_name, "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate LandGuard AI risk models.")
    parser.add_argument("--dataset", type=Path, default=Path("ml/data/synthetic_land_transactions.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("ml/models"))
    args = parser.parse_args()
    print(json.dumps(train_models(args.dataset, args.model_dir), indent=2))


if __name__ == "__main__":
    main()
