"""
Borrower-level risk score — XGBoost regressor on aggregated portfolio features.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
MODEL_NAME = "borrower_risk_xgb"

FEATURE_ORDER = [
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

FEATURE_LABELS = {
    "credit_score": "Credit Score",
    "avg_days_to_pay": "Average Days To Pay",
    "payment_terms": "Payment Terms",
    "num_late_payments": "Historical Late Payments",
    "log_portfolio": "Portfolio Exposure",
    "open_invoice_count": "Open Invoice Count",
    "overdue_invoice_count": "Overdue Invoice Count",
    "weighted_delay_probability": "Weighted Delay Probability",
    "overdue_ratio": "Overdue Ratio",
}


def _load(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load(MODEL_NAME)
_scaler = _load(f"{MODEL_NAME}_scaler")


def build_features_from_request(data: dict) -> Optional[np.ndarray]:
    """
    Build vector from BorrowerFeatures payload (same layout as train_borrower.FEATURE_COLS).
    """
    invoices = data.get("invoices") or []
    if not invoices:
        return None

    credit = float(data.get("credit_score", 650))
    avg_dtp = float(data.get("avg_days_to_pay", 30))
    terms = float(data.get("payment_terms", 30))
    late = int(data.get("num_late_payments", 0))
    portfolio = float(data.get("portfolio_total_outstanding", 0))

    total_outstanding = sum(float(inv.get("amount") or 0) for inv in invoices)
    total_overdue = sum(
        float(inv.get("amount") or 0) for inv in invoices
        if str(inv.get("status", "")).lower() == "overdue"
    )
    open_count = len(invoices)
    overdue_count = sum(1 for inv in invoices if str(inv.get("status", "")).lower() == "overdue")

    w = []
    for inv in invoices:
        amt = float(inv.get("amount") or 0)
        dp = float(inv.get("delay_probability") or 0)
        w.append(dp * amt)
    weighted_delay = sum(w) / max(total_outstanding, 1.0)
    overdue_ratio = total_overdue / max(total_outstanding, 1.0)
    log_portfolio = np.log1p(max(portfolio, total_outstanding))

    return np.array([[
        credit,
        avg_dtp,
        terms,
        float(late),
        float(log_portfolio),
        float(open_count),
        float(overdue_count),
        float(weighted_delay),
        float(overdue_ratio),
    ]])


def predict_borrower_risk(data: dict) -> Optional[dict]:
    if _model is None or _scaler is None:
        return None
    X = build_features_from_request(data)
    if X is None:
        return None
    try:
        scaled = _scaler.transform(X)
        score = float(np.clip(_model.predict(scaled)[0], 0, 100))
        tier = "High" if score >= 65 else ("Medium" if score >= 35 else "Low")
        drivers = top_feature_drivers(
            _model,
            _scaler,
            X,
            FEATURE_ORDER,
            top_n=5,
            display_names=FEATURE_LABELS,
        )
        return {
            "borrower_risk_score": round(score, 2),
            "borrower_risk_tier": tier,
            "feature_drivers": drivers,
            "explanation": summarize_drivers(drivers, "borrower risk score"),
        }
    except Exception:
        return None
