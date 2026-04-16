"""
Payment Probability Inference Module — INR Edition.

Loads XGBoost models trained on 1500-record INR dataset.
Builds the same 18-feature vector used during training (9 raw + 9 engineered).
Falls back to heuristic if models not found.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"

# Must match FEATURE_COLS + ENGINEERED_COLS in train_payment.py exactly
FEATURE_ORDER = [
    # Raw features (9)
    "invoice_amount",
    "days_overdue",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_previous_invoices",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
    # Engineered features (9)
    "overdue_ratio",
    "late_payment_rate",
    "log_amount",
    "log_overdue_ar",
    "credit_norm",
    "overdue_band",
    "amount_tier",
    "credit_x_overdue",
    "log_stress",
]

# Industry name → integer code mapping (INR dataset uses 10 industries)
INDUSTRY_MAP = {
    "manufacturing":  0,
    "it":             1,
    "technology":     1,
    "it/technology":  1,
    "healthcare":     2,
    "retail":         3,
    "retail/fmcg":    3,
    "fmcg":           3,
    "logistics":      4,
    "real estate":    5,
    "construction":   6,
    "agriculture":    7,
    "finance":        8,
    "nbfc":           8,
    "finance/nbfc":   8,
    "pharma":         9,
    "unknown":        1,   # default to IT (middle-risk industry)
}


def _load(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


# Lazy-load at module level (shared across requests)
_model_7d  = _load("payment_model_7d")
_scaler_7d = _load("payment_model_7d_scaler")
_model_15d = _load("payment_model_15d")
_scaler_15d = _load("payment_model_15d_scaler")
_model_30d = _load("payment_model_30d")
_scaler_30d = _load("payment_model_30d_scaler")


def build_features(data: dict) -> np.ndarray:
    """
    Build the 18-feature vector matching the training pipeline.
    Handles INR amounts (log-transform normalises scale for large values).
    """
    amount        = float(data.get("invoice_amount", 0))
    overdue       = float(data.get("days_overdue", 0))
    credit        = float(data.get("customer_credit_score", 650))
    avg_dtp       = float(data.get("customer_avg_days_to_pay", 30))
    terms         = float(data.get("payment_terms", 30))
    num_prev      = float(data.get("num_previous_invoices", 10))
    num_late      = float(data.get("num_late_payments", 0))
    total_overdue = float(data.get("customer_total_overdue", 0))

    # Industry code
    industry_str  = str(data.get("industry", "unknown")).lower()
    industry_code = float(INDUSTRY_MAP.get(industry_str, 1))

    # ── Engineered features (must match training exactly) ─────────────────────
    overdue_ratio     = overdue / max(terms, 1)
    late_payment_rate = num_late / max(num_prev, 1)
    log_amount        = np.log1p(amount)
    log_overdue_ar    = np.log1p(total_overdue)

    # CIBIL normalisation (300–900 → 0–1)
    credit_norm       = (credit - 300) / 600

    # Overdue band: 0=current, 1=1-30d, 2=31-60d, 3=61-90d, 4=90d+
    if overdue == 0:
        overdue_band = 0
    elif overdue <= 30:
        overdue_band = 1
    elif overdue <= 60:
        overdue_band = 2
    elif overdue <= 90:
        overdue_band = 3
    else:
        overdue_band = 4

    # Amount tier for INR — log-normalised during training
    if amount <= 100_000:
        amount_tier = 0
    elif amount <= 500_000:
        amount_tier = 1
    elif amount <= 2_000_000:
        amount_tier = 2
    elif amount <= 10_000_000:
        amount_tier = 3
    else:
        amount_tier = 4

    credit_x_overdue  = credit_norm * overdue_ratio
    stress_ratio      = total_overdue / max(amount, 1)
    log_stress        = np.log1p(stress_ratio)

    return np.array([[
        amount, overdue, credit, avg_dtp, terms,
        num_prev, num_late, industry_code, total_overdue,
        overdue_ratio, late_payment_rate, log_amount, log_overdue_ar,
        credit_norm, overdue_band, amount_tier, credit_x_overdue, log_stress,
    ]])


def _heuristic_payment_probs(data: dict) -> tuple[float, float, float]:
    """Rule-based payment probabilities when a horizon model is missing or errors."""
    credit = float(data.get("customer_credit_score", 650))
    overdue = float(data.get("days_overdue", 0))
    late = float(data.get("num_late_payments", 0))
    base = max(0.0, 1.0 - overdue / 90)
    cf = credit / 900
    pen = late * 0.05
    p7 = round(max(0.0, min(1.0, base * cf * 0.5 - pen)), 4)
    p15 = round(max(0.0, min(1.0, base * cf * 0.7 - pen)), 4)
    p30 = round(max(0.0, min(1.0, base * cf * 0.9 - pen)), 4)
    return p7, p15, p30


def predict(data: dict) -> dict:
    """
    Return payment probabilities for 7, 15, and 30-day horizons.
    Uses XGBoost per horizon when available; otherwise heuristic for that horizon only.
    """
    features = build_features(data)

    def safe_predict(model, scaler) -> Optional[float]:
        if model is None or scaler is None:
            return None
        try:
            scaled = scaler.transform(features)
            proba = model.predict_proba(scaled)[0][1]
            return float(round(proba, 4))
        except Exception:
            return None

    u7 = safe_predict(_model_7d, _scaler_7d)
    u15 = safe_predict(_model_15d, _scaler_15d)
    u30 = safe_predict(_model_30d, _scaler_30d)
    h7, h15, h30 = _heuristic_payment_probs(data)

    p7 = u7 if u7 is not None else h7
    p15 = u15 if u15 is not None else h15
    p30 = u30 if u30 is not None else h30

    ml_count = sum(1 for x in (u7, u15, u30) if x is not None)
    if ml_count == 3:
        model_version = "xgboost-v1"
    elif ml_count == 0:
        model_version = "heuristic-fallback-v1"
    else:
        model_version = "xgboost-partial-v1"

    return {
        "pay_7_days": p7,
        "pay_15_days": p15,
        "pay_30_days": p30,
        "model_version": model_version,
    }
