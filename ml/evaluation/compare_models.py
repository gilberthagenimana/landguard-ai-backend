"""Model comparison and evaluation utilities for LandGuard AI.

This module provides functions to compare trained models and generate
evaluation reports for the graduation project documentation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_metrics(model_dir: Path) -> dict[str, Any]:
    """Load metrics.json from a model directory."""
    metrics_path = model_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics file not found: {metrics_path}")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def compare_models(model_dir: Path) -> str:
    """Generate a human-readable comparison report of all trained models.

    Args:
        model_dir: Path to the directory containing metrics.json.

    Returns:
        A formatted string with model comparison table.
    """
    data = load_metrics(model_dir)
    metrics = data.get("metrics", {})
    selected = data.get("selected_model", "unknown")

    lines = [
        "=" * 70,
        "LandGuard AI — Model Comparison Report",
        "=" * 70,
        f"Selected Model: {selected}",
        "-" * 70,
        f"{'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}",
        "-" * 70,
    ]

    for name, values in metrics.items():
        marker = " <<<" if name == selected else ""
        lines.append(
            f"{name:<25} {values['accuracy']:>10.4f} {values['precision_weighted']:>10.4f} "
            f"{values['recall_weighted']:>10.4f} {values['f1_weighted']:>10.4f}{marker}"
        )

    lines.extend([
        "-" * 70,
        "Note: Weighted F1 is used for model selection due to class imbalance.",
        "Accuracy alone is insufficient because the dataset has imbalanced classes.",
        "=" * 70,
    ])

    return "\n".join(lines)


def main() -> None:
    """Print the model comparison report."""
    model_dir = Path(__file__).resolve().parents[2] / "models"
    print(compare_models(model_dir))


if __name__ == "__main__":
    main()
