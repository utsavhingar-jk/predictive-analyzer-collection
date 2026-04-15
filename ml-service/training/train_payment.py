"""
XGBoost Payment Probability Training Pipeline.

Trains three binary classifiers — one per time horizon (7, 15, 30 days) —
on the invoice dataset. Serializes trained models to the serialized_models/ directory.

Usage:
    python training/train_payment.py
"""

import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ─── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "invoices.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_DIR.mkdir(exist_ok=True)

# ─── Feature Configuration ───────────────────────────────────────────────────

FEATURE_COLS = [
    "invoice_amount",
    "days_overdue",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_previous_invoices",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
]

TARGETS = {
    "paid_in_7": "payment_model_7d",
    "paid_in_15": "payment_model_15d",
    "paid_in_30": "payment_model_30d",
}

XGB_PARAMS = {
    "max_depth": 4,
    "learning_rate": 0.1,
    "n_estimators": 200,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "use_label_encoder": False,
    "eval_metric": "logloss",
    "random_state": 42,
}


def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} records from {path}")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived features to improve model performance."""
    df = df.copy()
    df["overdue_ratio"] = df["days_overdue"] / df["payment_terms"].clip(lower=1)
    df["late_payment_rate"] = df["num_late_payments"] / df["num_previous_invoices"].clip(lower=1)
    df["log_amount"] = np.log1p(df["invoice_amount"])
    df["log_overdue_ar"] = np.log1p(df["customer_total_overdue"])
    return df


def train_model(df: pd.DataFrame, target_col: str, model_name: str) -> None:
    """Train a single XGBoost binary classifier and save to disk."""
    feature_cols = FEATURE_COLS + ["overdue_ratio", "late_payment_rate", "log_amount", "log_overdue_ar"]
    X = df[feature_cols].fillna(0)
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = xgb.XGBClassifier(**XGB_PARAMS)
    model.fit(
        X_train_scaled,
        y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False,
    )

    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\n[{model_name}] AUC-ROC: {auc:.4f}")
    print(classification_report(y_test, model.predict(X_test_scaled)))

    # Serialize model + scaler
    model_path = MODEL_DIR / f"{model_name}.pkl"
    scaler_path = MODEL_DIR / f"{model_name}_scaler.pkl"

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)

    # Save feature list and metadata
    meta = {
        "model_name": model_name,
        "target": target_col,
        "features": feature_cols,
        "auc_roc": round(auc, 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "xgb_params": XGB_PARAMS,
    }
    with open(MODEL_DIR / f"{model_name}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {model_path}")


def main() -> None:
    print("=" * 60)
    print("AI Collector — Payment Probability Training Pipeline")
    print("=" * 60)

    df = load_data(DATASET_PATH)
    df = engineer_features(df)

    for target_col, model_name in TARGETS.items():
        train_model(df, target_col, model_name)

    print("\nAll payment models trained successfully.")


if __name__ == "__main__":
    main()
