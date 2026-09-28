# ML Notebooks

This directory is reserved for Jupyter notebooks used during exploratory data analysis (EDA) and model development.

## Intended Notebooks

1. **`01_eda.ipynb`** — Exploratory analysis of the synthetic dataset (distributions, correlations, class balance).
2. **`02_feature_engineering.ipynb`** — Feature creation and selection experiments.
3. **`03_model_comparison.ipynb`** — Side-by-side training and evaluation of Logistic Regression, Decision Tree, and Random Forest.

## How to Create Notebooks

```powershell
pip install jupyter
jupyter notebook ml/notebooks/
```

> **Note**: Notebooks are for interactive analysis only. The production training pipeline lives in `ml/training/train.py` and `ml/predict.py`.
