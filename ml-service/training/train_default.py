"""
XGBoost default-proxy training pipeline.

Target:
  probability the invoice remains unpaid after 30 days
  -> trained as binary classification on (1 - paid_in_30)
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

MODEL_NAME = "default_model_30d"

FEATURE_COLS = [
    "invoice_amount",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_previous_invoices",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
]

XGB_PARAMS = {
    "max_depth": 5,
    "learning_rate": 0.08,
    "n_estimators": 300,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "eval_metric": "logloss",
    "random_state": 42,
}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["terms_gap_days"] = df["customer_avg_days_to_pay"] - df["payment_terms"]
    df["terms_stress"] = df["terms_gap_days"].clip(lower=0) / df["payment_terms"].clip(lower=1)
    df["late_payment_rate"] = df["num_late_payments"] / df["num_previous_invoices"].clip(lower=1)
    df["log_amount"] = np.log1p(df["invoice_amount"])
    df["log_overdue_ar"] = np.log1p(df["customer_total_overdue"])
    df["credit_norm"] = (df["customer_credit_score"] - 300) / 600
    df["amount_tier"] = pd.cut(
        df["invoice_amount"],
        bins=[0, 100_000, 500_000, 2_000_000, 10_000_000, float("inf")],
        labels=[0, 1, 2, 3, 4],
    ).astype(int)
    df["exposure_ratio"] = df["customer_total_overdue"] / df["invoice_amount"].clip(lower=1)
    df["credit_x_terms_stress"] = df["credit_norm"] * df["terms_stress"]
    return df


ENGINEERED_COLS = [
    "terms_gap_days",
    "terms_stress",
    "late_payment_rate",
    "log_amount",
    "log_overdue_ar",
    "credit_norm",
    "amount_tier",
    "exposure_ratio",
    "credit_x_terms_stress",
]


def main() -> None:
    print("=" * 60)
    print("AI Collector — Default Probability Training")
    print("=" * 60)

    df = pd.read_csv(DATASET_PATH)
    print(f"Loaded {len(df)} records")
    df = engineer_features(df)

    all_features = FEATURE_COLS + ENGINEERED_COLS
    X = df[all_features].fillna(0)
    y = 1 - df["paid_in_30"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    spw = neg / pos if pos > 0 else 1.0

    model = xgb.XGBClassifier(**XGB_PARAMS, scale_pos_weight=spw)
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    y_pred_proba = model.predict_proba(X_test_s)[:, 1]
    auc = roc_auc_score(y_test, y_pred_proba)
    print(f"AUC-ROC: {auc:.4f}  |  scale_pos_weight: {spw:.2f}")
    print(classification_report(y_test, model.predict(X_test_s)))

    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "target": "not_paid_in_30",
        "features": all_features,
        "auc_roc": round(auc, 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "dataset_rows": len(df),
        "xgb_params": XGB_PARAMS,
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {MODEL_DIR / MODEL_NAME}.pkl")


if __name__ == "__main__":
    main()
