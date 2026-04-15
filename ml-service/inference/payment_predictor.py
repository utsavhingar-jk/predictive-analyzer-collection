"""
Payment Probability Inference Module.

Loads trained XGBoost models and returns payment probability for
7, 15, and 30-day horizons given invoice features.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"

FEATURE_ORDER = [
    "invoice_amount",
    "days_overdue",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_previous_invoices",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
    "overdue_ratio",
    "late_payment_rate",
    "log_amount",
    "log_overdue_ar",
]

INDUSTRY_MAP = {
    "manufacturing": 0,
    "logistics": 1,
    "retail": 2,
    "technology": 3,
    "energy": 4,
    "healthcare": 5,
    "finance": 6,
    "unknown": 7,
}


def _load_model(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def _load_scaler(name: str):
    path = MODEL_DIR / f"{name}_scaler.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


# Lazy-load models at module level so they're shared across requests
_model_7d = _load_model("payment_model_7d")
_scaler_7d = _load_scaler("payment_model_7d")
_model_15d = _load_model("payment_model_15d")
_scaler_15d = _load_scaler("payment_model_15d")
_model_30d = _load_model("payment_model_30d")
_scaler_30d = _load_scaler("payment_model_30d")


def build_features(data: dict) -> np.ndarray:
    """Convert raw invoice dict to ordered feature array with derived features."""
    amount = float(data.get("invoice_amount", 0))
    overdue = float(data.get("days_overdue", 0))
    terms = float(data.get("payment_terms", 30))
    prev = float(data.get("num_previous_invoices", 0))
    late = float(data.get("num_late_payments", 0))
    total_overdue = float(data.get("customer_total_overdue", 0))
    industry = INDUSTRY_MAP.get(str(data.get("industry", "unknown")).lower(), 7)

    overdue_ratio = overdue / max(terms, 1)
    late_payment_rate = late / max(prev, 1)
    log_amount = np.log1p(amount)
    log_overdue_ar = np.log1p(total_overdue)

    return np.array([[
        amount,
        overdue,
        float(data.get("customer_credit_score", 650)),
        float(data.get("customer_avg_days_to_pay", 30)),
        terms,
        prev,
        late,
        float(industry),
        total_overdue,
        overdue_ratio,
        late_payment_rate,
        log_amount,
        log_overdue_ar,
    ]])


def predict(data: dict) -> dict:
    """
    Return payment probabilities for 7, 15, and 30-day horizons.

    Falls back to heuristic values if models are not trained yet.
    """
    features = build_features(data)

    def safe_predict(model, scaler) -> Optional[float]:
        if model is None or scaler is None:
            return None
        scaled = scaler.transform(features)
        proba = model.predict_proba(scaled)[0][1]
        return float(round(proba, 4))

    p7 = safe_predict(_model_7d, _scaler_7d)
    p15 = safe_predict(_model_15d, _scaler_15d)
    p30 = safe_predict(_model_30d, _scaler_30d)

    if p7 is None:
        # Heuristic fallback when models are not trained
        credit = float(data.get("customer_credit_score", 650))
        overdue = float(data.get("days_overdue", 0))
        late = float(data.get("num_late_payments", 0))

        base = max(0.0, 1.0 - overdue / 90)
        credit_factor = credit / 850
        penalty = late * 0.05

        p7 = round(max(0.0, min(1.0, base * credit_factor * 0.5 - penalty)), 4)
        p15 = round(max(0.0, min(1.0, base * credit_factor * 0.7 - penalty)), 4)
        p30 = round(max(0.0, min(1.0, base * credit_factor * 0.9 - penalty)), 4)

    return {"pay_7_days": p7, "pay_15_days": p15, "pay_30_days": p30}
