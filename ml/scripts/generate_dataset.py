from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DISCLAIMER = "Synthetic data created for academic development and testing; not official land records."


def generate_dataset(rows: int = 1200, seed: int = 42) -> pd.DataFrame:
    if rows < 100:
        raise ValueError("rows must be at least 100")

    rng = np.random.default_rng(seed)
    seller_owner_match = rng.binomial(1, 0.84, rows)
    duplicate_transaction = rng.binomial(1, 0.12, rows)
    recent_ownership_change = rng.binomial(1, 0.18, rows)
    record_inconsistency = rng.binomial(1, 0.10, rows)
    ownership_changes = rng.poisson(0.7, rows)
    previous_transactions = rng.poisson(1.8, rows)
    transaction_frequency_30d = rng.poisson(0.8, rows)
    days_since_previous_transaction = rng.integers(0, 1501, rows)
    transaction_value_log = rng.normal(16.0, 1.1, rows).clip(12.0, 20.0)

    risk_signal = (
        3.0 * (1 - seller_owner_match)
        + 3.5 * duplicate_transaction
        + 2.0 * recent_ownership_change
        + 2.5 * record_inconsistency
        + 0.45 * ownership_changes
        + 0.20 * transaction_frequency_30d
        + 0.10 * previous_transactions
        + (days_since_previous_transaction < 30) * 1.0
        + rng.normal(0, 0.7, rows)
    )
    risk_score = np.clip((risk_signal / 13.5) * 100, 0, 100)
    risk_level = np.select(
        [risk_score >= 60, risk_score >= 30],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )

    return pd.DataFrame(
        {
            "seller_owner_match": seller_owner_match,
            "duplicate_transaction": duplicate_transaction,
            "recent_ownership_change": recent_ownership_change,
            "record_inconsistency": record_inconsistency,
            "ownership_changes": ownership_changes,
            "previous_transactions": previous_transactions,
            "transaction_frequency_30d": transaction_frequency_30d,
            "days_since_previous_transaction": days_since_previous_transaction,
            "transaction_value_log": transaction_value_log,
            "risk_score": risk_score.round(2),
            "risk_level": risk_level,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic LandGuard AI transaction data.")
    parser.add_argument("--output", type=Path, default=Path("ml/data/synthetic_land_transactions.csv"))
    parser.add_argument("--rows", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = generate_dataset(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(args.output, index=False)
    print(f"Wrote {len(dataset)} synthetic rows to {args.output}")
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
