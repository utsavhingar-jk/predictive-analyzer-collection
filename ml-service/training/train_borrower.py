"""
XGBoost regressor for borrower risk score (0–100).

Inference: inference/borrower_predictor.py (FEATURE_ORDER must match FEATURE_COLS below).

**Production training (your data — recommended)**

1. Build one row per borrower with your features + a real ``borrower_risk_score_target`` (0–100),
   e.g. from outcomes: write-off %, recovery within 90d, internal risk grade mapped to 0–100.
2. Save as ``datasets/borrower_training.csv`` (or any path) and run:

     python training/train_borrower.py --csv path/to/your_borrower_training.csv

   Or set env ``BORROWER_TRAINING_CSV`` to that path.

3. See ``datasets/borrower_training.example.csv`` for required columns. You may omit
   ``log_portfolio`` if ``portfolio_total_outstanding`` is present (it will be computed).

**Demo / synthetic only** (not for accurate production results):

     python training/train_borrower.py --demo-invoices

   Aggregates ``datasets/invoices.csv`` with proxy labels. Prefer building
   ``datasets/borrower_training.csv`` via ``datasets/generate_borrower_training.py``;
   ``train_all.py`` runs that script and trains without ``--demo-invoices``.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent
DEFAULT_INVOICES = ROOT / "datasets" / "invoices.csv"
DEFAULT_CUSTOM_CSV = ROOT / "datasets" / "borrower_training.csv"
MODEL_DIR = ROOT / "serialized_models"
MODEL_NAME = "borrower_risk_xgb"


def borrower_heuristic_score(
    weighted_delay_probability: float,
    overdue_ratio: float,
    credit_score: float,
    num_late_payments: int,
    concentration_factor: float,
) -> float:
    """Same structure as ml-service main.py predict_borrower_endpoint → 0–100."""
    credit_factor = max(0.0, (700 - credit_score) / 400)
    late_factor = min(1.0, num_late_payments / 10)
    score_raw = (
        weighted_delay_probability * 0.40
        + overdue_ratio * 0.20
        + credit_factor * 0.20
        + late_factor * 0.10
        + concentration_factor * 0.10
    )
    return float(min(100, round(score_raw * 100)))


def aggregate_invoices(df: pd.DataFrame) -> pd.DataFrame:
    if "delay_probability_target" not in df.columns:
        raise SystemExit(
            "Column delay_probability_target missing. Regenerate:\n  python datasets/generate_dataset.py"
        )
    if "risk_label" not in df.columns:
        raise SystemExit(
            "Column risk_label missing in invoices CSV (needed for training labels)."
        )

    out = []
    for _cid, g in df.groupby("customer_id"):
        total_outstanding = float(g["invoice_amount"].sum())
        total_overdue = float(g.loc[g["days_overdue"] > 0, "invoice_amount"].sum())
        open_count = int(len(g))
        overdue_count = int((g["days_overdue"] > 0).sum())
        wdp = float(g["delay_probability_target"].mean())
        credit = float(g["customer_credit_score"].mean())
        avg_dtp = float(g["customer_avg_days_to_pay"].mean())
        terms = float(g["payment_terms"].mean())
        late = int(g["num_late_payments"].sum())
        portfolio = total_outstanding
        conc = min(1.0, (total_outstanding / max(portfolio, 1.0)) / 0.5)
        overdue_ratio = total_overdue / max(total_outstanding, 1.0)

        heur = borrower_heuristic_score(wdp, overdue_ratio, credit, late, conc)
        # Invoice-level severity (0=Low, 1=Med, 2=High) → 0–100 scale
        risk_mean = float(g["risk_label"].mean())
        risk_component = (risk_mean / 2.0) * 100.0
        delay_component = wdp * 100.0
        # Composite target: heuristic + risk tier + delay stress (weights tuned for learnability)
        y = 0.42 * heur + 0.32 * risk_component + 0.26 * delay_component
        y = float(max(0.0, min(100.0, round(y))))

        out.append({
            "credit_score": credit,
            "avg_days_to_pay": avg_dtp,
            "payment_terms": terms,
            "num_late_payments": late,
            "portfolio_total_outstanding": portfolio,
            "total_outstanding": total_outstanding,
            "open_invoice_count": open_count,
            "overdue_invoice_count": overdue_count,
            "weighted_delay_probability": wdp,
            "overdue_ratio": overdue_ratio,
            "borrower_risk_score_target": y,
        })
    return pd.DataFrame(out)


FEATURE_COLS = [
    "credit_score",
    "avg_days_to_pay",
    "payment_terms",
    "num_late_payments",
    "log_portfolio",
    "open_invoice_count",
    "overdue_invoice_count",
    "weighted_delay_probability",
    "overdue_ratio",
]

XGB_PARAMS = {
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 600,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "random_state": 42,
    "early_stopping_rounds": 40,
}


def _resolve_training_csv_path(explicit_csv: Path | None) -> Path | None:
    """Prefer env, then explicit --csv, then default datasets/borrower_training.csv if present."""
    env_csv = os.environ.get("BORROWER_TRAINING_CSV", "").strip()
    if env_csv:
        p = Path(env_csv)
        if p.is_file():
            return p
        raise SystemExit(f"BORROWER_TRAINING_CSV is set but file not found: {p}")
    if explicit_csv is not None:
        if explicit_csv.is_file():
            return explicit_csv
        raise SystemExit(f"--csv file not found: {explicit_csv}")
    if DEFAULT_CUSTOM_CSV.is_file():
        return DEFAULT_CUSTOM_CSV
    return None


def load_training_frame(
    invoices_path: Path,
    training_csv: Path | None,
    demo_invoices: bool,
) -> tuple[pd.DataFrame, str]:
    """Returns (dataframe with FEATURE_COLS + target, label_description)."""
    if training_csv is not None and training_csv.is_file():
        agg = pd.read_csv(training_csv)
        if "log_portfolio" not in agg.columns and "portfolio_total_outstanding" in agg.columns:
            agg["log_portfolio"] = np.log1p(agg["portfolio_total_outstanding"].clip(lower=0))
        need = set(FEATURE_COLS) | {"borrower_risk_score_target"}
        missing = need - set(agg.columns)
        if missing:
            raise SystemExit(
                f"Training CSV missing columns: {sorted(missing)}\n"
                f"Required: {sorted(need)}\n"
                f"See: {ROOT / 'datasets' / 'borrower_training.example.csv'}"
            )
        desc = f"your dataset ({training_csv.name}) — borrower_risk_score_target must reflect real outcomes for accuracy"
        return agg, desc

    if demo_invoices:
        df = pd.read_csv(invoices_path)
        agg = aggregate_invoices(df)
        desc = (
            "DEMO: aggregated from invoices.csv with proxy labels — "
            "use --csv with your borrower_training.csv for production"
        )
        return agg, desc

    raise SystemExit(
        "\nNo borrower training file found.\n\n"
        "To train on YOUR data (recommended):\n"
        f"  1. Create a CSV with columns listed in datasets/borrower_training.example.csv\n"
        f"  2. Save as {DEFAULT_CUSTOM_CSV} OR pass --csv /path/to/your.csv\n"
        f"     Or set environment variable BORROWER_TRAINING_CSV=/path/to/your.csv\n\n"
        "For demo only (synthetic proxy labels from invoices.csv):\n"
        "  python training/train_borrower.py --demo-invoices\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train borrower_risk_xgb on YOUR labeled borrower rows")
    parser.add_argument(
        "--invoices",
        type=Path,
        default=DEFAULT_INVOICES,
        help="With --demo-invoices only: source invoices.csv to aggregate",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Your training CSV path (ignored if BORROWER_TRAINING_CSV env is set)",
    )
    parser.add_argument(
        "--demo-invoices",
        action="store_true",
        help="Train from aggregated synthetic invoices.csv (not for production accuracy)",
    )
    args = parser.parse_args()

    training_csv = _resolve_training_csv_path(args.csv)

    print("=" * 60)
    print("Borrower risk score — XGBoost regressor")
    print("=" * 60)

    if args.demo_invoices and training_csv is not None:
        print("Note: using your training CSV; --demo-invoices ignored.\n")

    if training_csv is not None:
        agg, label_desc = load_training_frame(
            args.invoices, training_csv, demo_invoices=False
        )
    elif args.demo_invoices:
        agg, label_desc = load_training_frame(
            args.invoices, None, demo_invoices=True
        )
    else:
        load_training_frame(args.invoices, None, demo_invoices=False)

    print(f"Label source: {label_desc}")

    if "log_portfolio" not in agg.columns:
        if "portfolio_total_outstanding" not in agg.columns:
            raise SystemExit("Training data needs log_portfolio or portfolio_total_outstanding")
        agg["log_portfolio"] = np.log1p(agg["portfolio_total_outstanding"].clip(lower=0))

    X = agg[FEATURE_COLS].fillna(0)
    y = agg["borrower_risk_score_target"].clip(0, 100)

    if len(agg) < 2:
        raise SystemExit("Need at least 2 borrower rows in the training data.")
    if len(agg) < 5:
        print(
            f"Warning: only {len(agg)} rows — using 1-row hold-out; add more rows for reliable metrics.\n"
        )
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=1, random_state=42, shuffle=True
        )
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    params = {k: v for k, v in XGB_PARAMS.items() if k != "early_stopping_rounds"}
    es = XGB_PARAMS.get("early_stopping_rounds", 0)
    model = xgb.XGBRegressor(**params, objective="reg:squarederror")
    fit_kw: dict = {"eval_set": [(X_test_s, y_test)], "verbose": False}
    if es:
        fit_kw["early_stopping_rounds"] = es
    try:
        model.fit(X_train_s, y_train, **fit_kw)
    except TypeError:
        # Older xgboost without early_stopping in fit
        model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

    pred = model.predict(X_test_s).clip(0, 100)
    mae = mean_absolute_error(y_test, pred)
    r2 = r2_score(y_test, pred)
    print(f"MAE: {mae:.3f}  |  R²: {r2:.4f}  |  customer rows: {len(agg)}")

    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_DIR / f"{MODEL_NAME}.pkl", "wb") as f:
        pickle.dump(model, f)
    with open(MODEL_DIR / f"{MODEL_NAME}_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    meta = {
        "model_name": MODEL_NAME,
        "target": "borrower_risk_score_target",
        "label_description": label_desc,
        "features": FEATURE_COLS,
        "mae": round(mae, 4),
        "r2": round(r2, 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "xgb_params": params,
    }
    with open(MODEL_DIR / f"{MODEL_NAME}_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved: {MODEL_DIR / MODEL_NAME}.pkl")


if __name__ == "__main__":
    main()
