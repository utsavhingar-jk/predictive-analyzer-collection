"""
LightGBM Risk Classification Training Pipeline.

Trains a multi-class classifier to categorize invoices as:
  0 = Low Risk, 1 = Medium Risk, 2 = High Risk

Usage:
    python training/train_risk.py
"""

import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# ─── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "invoices.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_DIR.mkdir(exist_ok=True)

MODEL_NAME = "risk_classifier_lgbm"

FEATURE_COLS = [
    "invoice_amount",
    "days_overdue",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
]

LGBM_PARAMS = {
    "objective": "multiclass",
    "num_class": 3,
    "n_estimators": 300,
    "learning_rate": 0.05,
    "max_depth": 5,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}

LABEL_MAP = {0: "Low", 1: "Medium", 2: "High"}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["overdue_ratio"] = df["days_overdue"] / df["payment_terms"].clip(lower=1)
    prev = df["num_previous_invoices"] if "num_previous_invoices" in df.columns else 1
    df["late_payment_rate"] = df["num_late_payments"] / pd.Series(prev).clip(lower=1).values
    df["log_amount"] = np.log1p(df["invoice_amount"])
    df["log_overdue_ar"] = np.log1p(df["customer_total_overdue"])
    return df


def main() -> None:
    print("=" * 60)
    print("AI Collector — Risk Classification Training Pipeline")
    print("=" * 60)

    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} records.")
    df = engineer_features(df)

    feature_cols = FEATURE_COLS + ["overdue_ratio", "late_payment_rate", "log_amount", "log_overdue_ar"]
    X = df[feature_cols].fillna(0)
    y = df["risk_label"]  # 0=Low, 1=Medium, 2=High

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(X_train_s, y_train)

    y_pred = model.predict(X_test_s)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Low", "Medium", "High"]))

    # Serialize
    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)

    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "target": "risk_label",
        "label_map": LABEL_MAP,
        "features": feature_cols,
        "lgbm_params": LGBM_PARAMS,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSaved: {MODEL_DIR / MODEL_NAME}.pkl")
    print("Risk classifier trained successfully.")


if __name__ == "__main__":
    main()
