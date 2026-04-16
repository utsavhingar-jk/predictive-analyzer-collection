"""
XGBoost multiclass for payment behavior (6 classes).

Data: datasets/behavior_training.csv from generate_behavior_dataset.py
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "behavior_training.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_NAME = "behavior_classifier_xgb"

FEATURE_COLS = [
    "historical_on_time_ratio",
    "avg_delay_days",
    "repayment_consistency",
    "partial_payment_frequency",
    "prior_delayed_invoice_count",
    "payment_after_followup_count",
    "total_invoices",
    "deterioration_trend",
    "transaction_success_failure_pattern",
    "invoice_acknowledgement_encoded",
]

XGB_PARAMS = {
    "objective": "multi:softprob",
    "num_class": 6,
    "max_depth": 5,
    "learning_rate": 0.08,
    "n_estimators": 350,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "eval_metric": "mlogloss",
    "random_state": 42,
}


def main() -> None:
    print("=" * 60)
    print("Payment behavior — XGBoost (6 classes)")
    print("=" * 60)

    if not DATASET_PATH.exists():
        raise SystemExit(
            f"Missing {DATASET_PATH}\nRun: python datasets/generate_behavior_dataset.py"
        )

    df = pd.read_csv(DATASET_PATH)
    X = df[FEATURE_COLS].fillna(0)
    y = df["behavior_class"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = xgb.XGBClassifier(**XGB_PARAMS)
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    y_pred = model.predict(X_test_s)
    names = ["CP", "OLP", "RDP", "PPP", "CDP", "HRD"]
    labels = list(range(6))
    print(classification_report(y_test, y_pred, labels=labels, target_names=names, zero_division=0))

    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "features": FEATURE_COLS,
        "num_class": 6,
        "xgb_params": XGB_PARAMS,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {MODEL_DIR / MODEL_NAME}.pkl")


if __name__ == "__main__":
    main()
