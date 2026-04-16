"""
XGBoost Payment Probability Training Pipeline — INR Edition.

Trains three binary classifiers (one per time horizon: 7, 15, 30 days)
on a 1500-record INR dataset of Indian B2B invoices.

Changes from v1:
  - Amounts in INR — log-normalised to handle ₹25K–₹5Cr range
  - CIBIL score range (300–900) normalised
  - class_weight='balanced' via scale_pos_weight to handle imbalance
  - Additional engineered features: credit_bucket, overdue_band, amount_tier

Usage:
    python training/train_payment.py
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "invoices.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_DIR.mkdir(exist_ok=True)

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
    "paid_in_7":  "payment_model_7d",
    "paid_in_15": "payment_model_15d",
    "paid_in_30": "payment_model_30d",
}

XGB_PARAMS = {
    "max_depth":        5,
    "learning_rate":    0.08,
    "n_estimators":     300,
    "subsample":        0.85,
    "colsample_bytree": 0.85,
    "eval_metric":      "logloss",
    "random_state":     42,
    "use_label_encoder": False,
}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Core ratios
    df["overdue_ratio"]     = df["days_overdue"] / df["payment_terms"].clip(lower=1)
    df["late_payment_rate"] = df["num_late_payments"] / df["num_previous_invoices"].clip(lower=1)

    # Log transforms — important for INR amounts spanning 4 orders of magnitude
    df["log_amount"]        = np.log1p(df["invoice_amount"])
    df["log_overdue_ar"]    = np.log1p(df["customer_total_overdue"])

    # CIBIL normalised to 0–1 (300–900 range)
    df["credit_norm"]       = (df["customer_credit_score"] - 300) / 600

    # Overdue severity band
    df["overdue_band"] = pd.cut(
        df["days_overdue"],
        bins=[-1, 0, 30, 60, 90, 999],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)

    # Amount tier (INR-specific buckets)
    df["amount_tier"] = pd.cut(
        df["invoice_amount"],
        bins=[0, 100_000, 500_000, 2_000_000, 10_000_000, float("inf")],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)

    # Interaction: credit × overdue
    df["credit_x_overdue"] = df["credit_norm"] * df["overdue_ratio"]

    # Customer stress ratio
    df["stress_ratio"] = df["customer_total_overdue"] / df["invoice_amount"].clip(lower=1)
    df["log_stress"]   = np.log1p(df["stress_ratio"])

    return df


ENGINEERED_COLS = [
    "overdue_ratio", "late_payment_rate",
    "log_amount", "log_overdue_ar",
    "credit_norm", "overdue_band", "amount_tier",
    "credit_x_overdue", "log_stress",
]


def train_model(df: pd.DataFrame, target_col: str, model_name: str) -> None:
    all_features = FEATURE_COLS + ENGINEERED_COLS
    X = df[all_features].fillna(0)
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # Handle class imbalance with scale_pos_weight
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    spw = neg / pos if pos > 0 else 1.0

    model = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=spw)
    model.fit(
        X_train_s, y_train,
        eval_set=[(X_test_s, y_test)],
        verbose=False,
    )

    y_pred_proba = model.predict_proba(X_test_s)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\n[{model_name}]  AUC-ROC: {auc:.4f}  |  scale_pos_weight: {spw:.2f}")
    print(classification_report(y_test, model.predict(X_test_s)))

    with open(MODEL_DIR / f"{model_name}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{model_name}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name":    model_name,
        "target":        target_col,
        "features":      all_features,
        "auc_roc":       round(auc, 4),
        "n_train":       len(X_train),
        "n_test":        len(X_test),
        "currency":      "INR",
        "dataset_rows":  len(df),
        "xgb_params":    XGB_PARAMS,
    }
    with open(MODEL_DIR / f"{model_name}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {MODEL_DIR / model_name}.pkl")


def main() -> None:
    print("=" * 60)
    print("AI Collector — Payment Probability Training (INR, 1500 rows)")
    print("=" * 60)

    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} records | Currency: INR")
    df = engineer_features(df)

    for target_col, model_name in TARGETS.items():
        train_model(df, target_col, model_name)

    print("\nAll payment models trained successfully.")


if __name__ == "__main__":
    main()
