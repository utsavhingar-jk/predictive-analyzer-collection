"""
Payment Probability Inference Module — INR Edition.

Loads XGBoost models trained on a future-looking synthetic INR dataset.
Builds the same pre-outcome-safe feature vector used during training.
Falls back to heuristic if models not found.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"

# Must match FEATURE_COLS + ENGINEERED_COLS in train_payment.py exactly
FEATURE_ORDER = [
    # Raw features
    "invoice_amount",
    "customer_credit_score",
    "customer_avg_days_to_pay",
    "payment_terms",
    "num_previous_invoices",
    "num_late_payments",
    "industry_encoded",
    "customer_total_overdue",
    # Engineered features
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

FEATURE_LABELS = {
    "invoice_amount": "Invoice Amount",
    "customer_credit_score": "Customer Credit Score",
    "customer_avg_days_to_pay": "Customer Average Days To Pay",
    "payment_terms": "Payment Terms",
    "num_previous_invoices": "Previous Invoice Count",
    "num_late_payments": "Historical Late Payments",
    "industry_encoded": "Industry Segment",
    "customer_total_overdue": "Customer Total Overdue",
    "terms_gap_days": "Historical Days Beyond Terms",
    "terms_stress": "Payment Terms Stress",
    "late_payment_rate": "Late Payment Rate",
    "log_amount": "Log Invoice Amount",
    "log_overdue_ar": "Log Customer Overdue Exposure",
    "credit_norm": "Normalized Credit Score",
    "amount_tier": "Invoice Amount Tier",
    "exposure_ratio": "Outstanding Exposure Ratio",
    "credit_x_terms_stress": "Credit-Terms Stress Interaction",
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
    Build the pre-outcome-safe feature vector matching the training pipeline.
    """
    amount = float(data.get("invoice_amount", 0))
    credit = float(data.get("customer_credit_score", 650))
    avg_dtp = float(data.get("customer_avg_days_to_pay", 30))
    terms = float(data.get("payment_terms", 30))
    num_prev = float(data.get("num_previous_invoices", 10))
    num_late = float(data.get("num_late_payments", 0))
    total_overdue = float(data.get("customer_total_overdue", 0))

    # Industry code
    industry_str = str(data.get("industry", "unknown")).lower()
    industry_code = float(INDUSTRY_MAP.get(industry_str, 1))

    # ── Engineered features (must match training exactly) ─────────────────────
    terms_gap_days = avg_dtp - terms
    terms_stress = max(0.0, terms_gap_days) / max(terms, 1)
    late_payment_rate = num_late / max(num_prev, 1)
    log_amount = np.log1p(amount)
    log_overdue_ar = np.log1p(total_overdue)

    # CIBIL normalisation (300–900 → 0–1)
    credit_norm = (credit - 300) / 600

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

    exposure_ratio = total_overdue / max(amount, 1)
    credit_x_terms_stress = credit_norm * terms_stress

    return np.array([[
        amount, credit, avg_dtp, terms,
        num_prev, num_late, industry_code, total_overdue,
        terms_gap_days, terms_stress, late_payment_rate, log_amount, log_overdue_ar,
        credit_norm, amount_tier, exposure_ratio, credit_x_terms_stress,
    ]])


def _heuristic_payment_probs(data: dict) -> tuple[float, float, float]:
    """Rule-based payment probabilities using pre-outcome-safe historical signals."""
    credit = float(data.get("customer_credit_score", 650))
    avg_dtp = float(data.get("customer_avg_days_to_pay", 30))
    terms = max(1.0, float(data.get("payment_terms", 30)))
    amount = max(1.0, float(data.get("invoice_amount", 0)))
    total_overdue = max(0.0, float(data.get("customer_total_overdue", 0)))
    prev = max(1.0, float(data.get("num_previous_invoices", 1)))
    late = float(data.get("num_late_payments", 0))
    credit_norm = min(1.0, max(0.0, (credit - 300.0) / 600.0))
    terms_stress = max(0.0, avg_dtp - terms) / terms
    late_rate = min(1.0, late / prev)
    exposure_ratio = min(2.0, total_overdue / amount)

    delay_pressure = (
        terms_stress * 0.35
        + late_rate * 0.30
        + (1.0 - credit_norm) * 0.25
        + min(1.0, exposure_ratio) * 0.10
    )
    p30 = round(max(0.02, min(0.98, 0.90 - delay_pressure * 0.65)), 4)
    p15 = round(max(0.01, min(p30, p30 - 0.08 - terms_stress * 0.06)), 4)
    p7 = round(max(0.01, min(p15, p15 - 0.10 - late_rate * 0.05)), 4)
    return p7, p15, p30


def predict(data: dict) -> dict:
    """
    Return payment probabilities for 7, 15, and 30-day horizons.
    Uses XGBoost per horizon when available; otherwise heuristic for that horizon only.
    """
    features = build_features(data)

    def safe_predict(model, scaler, output_name: str) -> tuple[Optional[float], list[dict]]:
        if model is None or scaler is None:
            return None, []
        try:
            scaled = scaler.transform(features)
            proba = model.predict_proba(scaled)[0][1]
            drivers = top_feature_drivers(
                model,
                scaler,
                features,
                FEATURE_ORDER,
                top_n=5,
                class_index=0,
                display_names=FEATURE_LABELS,
            )
            return float(round(proba, 4)), drivers
        except Exception:
            return None, []

    u7, d7 = safe_predict(_model_7d, _scaler_7d, "pay_7_days")
    u15, d15 = safe_predict(_model_15d, _scaler_15d, "pay_15_days")
    u30, d30 = safe_predict(_model_30d, _scaler_30d, "pay_30_days")
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

    horizon_drivers = []
    if u7 is not None:
        horizon_drivers.append(
            {"output_name": "pay_7_days", "predicted_value": p7, "drivers": d7}
        )
    if u15 is not None:
        horizon_drivers.append(
            {"output_name": "pay_15_days", "predicted_value": p15, "drivers": d15}
        )
    if u30 is not None:
        horizon_drivers.append(
            {"output_name": "pay_30_days", "predicted_value": p30, "drivers": d30}
        )
    if u30 is not None and d30:
        explanation = summarize_drivers(d30, "payment within 30 days")
    elif horizon_drivers and horizon_drivers[0]["drivers"]:
        explanation = summarize_drivers(horizon_drivers[0]["drivers"], horizon_drivers[0]["output_name"])
    else:
        explanation = "Rule fallback was used because the trained payment model was unavailable."

    return {
        "pay_7_days": p7,
        "pay_15_days": p15,
        "pay_30_days": p30,
        "model_version": model_version,
        "feature_drivers_by_horizon": horizon_drivers,
        "explanation": explanation,
    }
