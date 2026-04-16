"""
XGBoost Risk Classification Training Pipeline — INR Edition.

Trains a multi-class classifier:
  0 = Low Risk, 1 = Medium Risk, 2 = High Risk

Usage:
    python training/train_risk.py
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

MODEL_NAME = "risk_classifier_xgb"

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
    "objective": "multi:softprob",
    "num_class": 3,
    "max_depth": 6,
    "learning_rate": 0.06,
    "n_estimators": 400,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "eval_metric": "mlogloss",
    "random_state": 42,
}

LABEL_MAP = {0: "Low", 1: "Medium", 2: "High"}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["overdue_ratio"] = df["days_overdue"] / df["payment_terms"].clip(lower=1)
    prev = df["num_previous_invoices"] if "num_previous_invoices" in df.columns else pd.Series([10] * len(df))
    df["late_payment_rate"] = df["num_late_payments"] / prev.clip(lower=1).values

    df["log_amount"] = np.log1p(df["invoice_amount"])
    df["log_overdue_ar"] = np.log1p(df["customer_total_overdue"])
    df["credit_norm"] = (df["customer_credit_score"] - 300) / 600

    df["overdue_band"] = pd.cut(
        df["days_overdue"],
        bins=[-1, 0, 30, 60, 90, 999],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)

    df["amount_tier"] = pd.cut(
        df["invoice_amount"],
        bins=[0, 100_000, 500_000, 2_000_000, 10_000_000, float("inf")],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)

    df["credit_x_overdue"] = df["credit_norm"] * df["overdue_ratio"]
    df["log_stress"] = np.log1p(df["customer_total_overdue"] / df["invoice_amount"].clip(lower=1))

    return df


ENGINEERED_COLS = [
    "overdue_ratio", "late_payment_rate",
    "log_amount", "log_overdue_ar",
    "credit_norm", "overdue_band", "amount_tier",
    "credit_x_overdue", "log_stress",
]


def main() -> None:
    print("=" * 60)
    print("AI Collector — Risk Classification Training (XGBoost, INR)")
    print("=" * 60)

    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} records | Currency: INR")
    df = engineer_features(df)

    counts = df["risk_label"].value_counts().sort_index()
    for k, v in counts.items():
        print(f"  {LABEL_MAP[k]:8s}: {v:4d}  ({v/len(df):.1%})")

    all_features = FEATURE_COLS + ENGINEERED_COLS
    X = df[all_features].fillna(0)
    y = df["risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = xgb.XGBClassifier(**LGBM_PARAMS)
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    y_pred = model.predict(X_test_s)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Low", "Medium", "High"]))

    proba = model.predict_proba(X_test_s)
    try:
        auc = roc_auc_score(y_test, proba, multi_class="ovr", average="weighted")
        print(f"Weighted OvR AUC: {auc:.4f}")
    except Exception:
        pass

    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "target": "risk_label",
        "label_map": {str(k): v for k, v in LABEL_MAP.items()},
        "features": all_features,
        "xgb_params": LGBM_PARAMS,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "currency": "INR",
        "dataset_rows": len(df),
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nSaved: {MODEL_DIR / MODEL_NAME}.pkl")
    print("Risk classifier trained successfully.")


if __name__ == "__main__":
    main()
