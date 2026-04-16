"""
XGBoost regressor for delay probability (same 18 features as payment predictor).

Label: delay_probability_target from datasets/invoices.csv (see generate_dataset.py).
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "invoices.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_DIR.mkdir(exist_ok=True)

MODEL_NAME = "delay_probability_xgb"

# Must match train_payment.py FEATURE_COLS + ENGINEERED_COLS
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


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["overdue_ratio"] = df["days_overdue"] / df["payment_terms"].clip(lower=1)
    df["late_payment_rate"] = df["num_late_payments"] / df["num_previous_invoices"].clip(lower=1)
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
    df["stress_ratio"] = df["customer_total_overdue"] / df["invoice_amount"].clip(lower=1)
    df["log_stress"] = np.log1p(df["stress_ratio"])
    return df


ENGINEERED_COLS = [
    "overdue_ratio", "late_payment_rate",
    "log_amount", "log_overdue_ar",
    "credit_norm", "overdue_band", "amount_tier",
    "credit_x_overdue", "log_stress",
]

XGB_PARAMS = {
    "max_depth": 6,
    "learning_rate": 0.06,
    "n_estimators": 400,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "random_state": 42,
}


def main() -> None:
    print("=" * 60)
    print("Delay probability — XGBoost regressor (18 features)")
    print("=" * 60)

    df = pd.read_csv(DATASET_PATH)
    if "delay_probability_target" not in df.columns:
        raise SystemExit(
            "Column delay_probability_target missing. Regenerate data:\n"
            "  python datasets/generate_dataset.py"
        )

    df = engineer_features(df)
    all_features = FEATURE_COLS + ENGINEERED_COLS
    X = df[all_features].fillna(0)
    y = df["delay_probability_target"].clip(0.01, 0.99)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = xgb.XGBRegressor(**XGB_PARAMS, objective="reg:squarederror")
    model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    pred = model.predict(X_test_s).clip(0.01, 0.99)
    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)
    print(f"MAE: {mae:.4f}  |  R²: {r2:.4f}")

    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "target": "delay_probability_target",
        "features": all_features,
        "mae": round(mae, 5),
        "r2": round(r2, 5),
        "xgb_params": XGB_PARAMS,
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {MODEL_DIR / MODEL_NAME}.pkl")


if __name__ == "__main__":
    main()
