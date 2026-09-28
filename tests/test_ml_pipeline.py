from pathlib import Path

import pytest

from ml.predict import predict_risk
from ml.scripts.generate_dataset import generate_dataset
from ml.training.train import FEATURES, train_models


def test_synthetic_dataset_is_reproducible_and_balanced():
    first = generate_dataset(rows=300, seed=7)
    second = generate_dataset(rows=300, seed=7)

    assert first.equals(second)
    assert set(FEATURES).issubset(first.columns)
    assert first["risk_level"].nunique() >= 2


def test_training_writes_selected_model_and_metrics(tmp_path: Path):
    dataset_path = tmp_path / "transactions.csv"
    model_dir = tmp_path / "models"
    generate_dataset(rows=300, seed=11).to_csv(dataset_path, index=False)

    result = train_models(dataset_path, model_dir)

    assert result["selected_model"] in {"logistic_regression", "decision_tree", "random_forest"}
    assert (model_dir / "risk_model.joblib").exists()
    assert (model_dir / "metrics.json").exists()


def test_prediction_rejects_missing_features(tmp_path: Path):
    with pytest.raises(ValueError, match="Missing risk features"):
        predict_risk({}, tmp_path / "missing.joblib")
