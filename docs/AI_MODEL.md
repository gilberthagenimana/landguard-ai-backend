# LandGuard AI — AI/ML Model Documentation

## 1. Overview

The AI component predicts transaction risk indicators. It does NOT classify people as criminals, determine legal ownership, or replace an authorized officer.

> **CRITICAL**: All training data is **synthetic** and clearly labeled as "DEMO/SYNTHETIC DATA - NOT OFFICIAL LAND RECORDS". The model is trained on artificially generated data for academic purposes only.

## 2. Model Details

| Property | Value |
|---|---|
| **Algorithm** | Random Forest Classifier |
| **Version** | random_forest-v2-synthetic |
| **Input Features** | 9 transaction-level features |
| **Output** | Risk level (LOW/MEDIUM/HIGH) + risk score (0-100) |
| **Training Data** | 1,200 synthetic rows |
| **Evaluation** | Accuracy: 87.92%, F1: 88.35% |

## 3. Input Features

| # | Feature | Description | Type |
|---|---|---|---|
| 1 | `seller_owner_match` | Seller matches latest recorded owner | Binary (0/1) |
| 2 | `duplicate_transaction` | Another active transaction exists | Binary (0/1) |
| 3 | `recent_ownership_change` | Ownership changed within 30 days | Binary (0/1) |
| 4 | `record_inconsistency` | Transaction info incomplete | Binary (0/1) |
| 5 | `ownership_changes` | Total ownership changes for parcel | Integer |
| 6 | `previous_transactions` | Number of previous transactions | Integer |
| 7 | `transaction_frequency_30d` | Transactions in last 30 days | Integer |
| 8 | `days_since_previous_transaction` | Days since last transaction | Integer |
| 9 | `transaction_value_log` | Log of declared value | Float |

## 4. Output

```json
{
  "transaction_id": 1,
  "risk_score": 55,
  "risk_level": "MEDIUM",
  "model_version": "random_forest-v2-synthetic",
  "reasons": [
    "Another active transaction exists for this parcel; review for a possible conflict.",
    "The seller does not match the latest recorded owner; verify the ownership records."
  ],
  "analyzed_at": "2026-10-09T10:00:00Z"
}
```

## 5. Model Training

```powershell
cd "D:\LandGuard AI\landguard-ai-backend"
python -m ml.training.train --dataset ml/data/synthetic_land_transactions.csv --model-dir ml/models
```

## 6. Model Evaluation

| Model | Accuracy | Precision | Recall | F1 |
|---|---|---|---|---|
| Logistic Regression | 87.08% | 91.19% | 87.08% | 88.10% |
| Decision Tree | 85.00% | 88.54% | 85.00% | 86.13% |
| **Random Forest** | **87.92%** | **89.09%** | **87.92%** | **88.35%** |

## 7. Limitations

1. **Synthetic data only** — Model is trained on artificially generated data, not real land records
2. **Limited features** — Only transaction-level features used; no external data sources
3. **No real-world validation** — Model has not been tested on actual land transaction data
4. **Risk indicators only** — AI output is advisory and does not prove fraud
5. **Human decision required** — Final determination always remains with authorized officers
6. **Cannot detect unreported sales** — System can only analyze data that has been entered

## 8. Retraining

To retrain the model with new data:

1. Prepare a CSV file with the 9 features + risk_level column
2. Run: `python -m ml.training.train --dataset <path> --model-dir ml/models`
3. The best model (by F1 score) will be saved as `ml/models/risk_model.joblib`
