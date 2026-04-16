"""
Risk Classification Inference Module — INR Edition.

Loads XGBoost (preferred) or legacy LightGBM classifier.
Builds the same 18-feature vector used during training.
Falls back to heuristic if model not found.
"""

import pickle
from pathlib import Path

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
LABEL_MAP = {0: "Low", 1: "Medium", 2: "High"}

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
    "unknown":        1,
}

FEATURE_LABELS = {
    "invoice_amount": "Invoice Amount",
    "days_overdue": "Days Overdue",
    "customer_credit_score": "Customer Credit Score",
    "customer_avg_days_to_pay": "Customer Average Days To Pay",
    "payment_terms": "Payment Terms",
    "num_late_payments": "Historical Late Payments",
    "industry_encoded": "Industry Segment",
    "customer_total_overdue": "Customer Total Overdue",
    "overdue_ratio": "Overdue Ratio",
    "late_payment_rate": "Late Payment Rate",
    "log_amount": "Log Invoice Amount",
    "log_overdue_ar": "Log Customer Overdue Exposure",
    "credit_norm": "Normalized Credit Score",
    "overdue_band": "Overdue Severity Band",
    "amount_tier": "Invoice Amount Tier",
    "credit_x_overdue": "Credit-Overdue Interaction",
    "log_stress": "Payment Stress Indicator",
}


def _load(name: str):
    path = MODEL_DIR / name
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_USE_XGB_RISK = (MODEL_DIR / "risk_classifier_xgb.pkl").exists()
_model = _load("risk_classifier_xgb.pkl") or _load("risk_classifier_lgbm.pkl")
_scaler = _load("risk_classifier_xgb_scaler.pkl") or _load("risk_classifier_lgbm_scaler.pkl")


def build_features(data: dict) -> np.ndarray:
    """18-feature vector — must match train_risk.py exactly."""
    amount        = float(data.get("invoice_amount", 0))
    overdue       = float(data.get("days_overdue", 0))
    credit        = float(data.get("customer_credit_score", 650))
    avg_dtp       = float(data.get("customer_avg_days_to_pay", 30))
    terms         = float(data.get("payment_terms", 30))
    num_late      = float(data.get("num_late_payments", 0))
    total_overdue = float(data.get("customer_total_overdue", 0))

    industry_str  = str(data.get("industry", "unknown")).lower()
    industry_code = float(INDUSTRY_MAP.get(industry_str, 1))

    num_prev = float(data.get("num_previous_invoices", 10))

    # Engineered
    overdue_ratio     = overdue / max(terms, 1)
    late_payment_rate = num_late / max(num_prev, 1)
    log_amount        = np.log1p(amount)
    log_overdue_ar    = np.log1p(total_overdue)
    credit_norm       = (credit - 300) / 600

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

    credit_x_overdue = credit_norm * overdue_ratio
    log_stress        = np.log1p(total_overdue / max(amount, 1))

    return np.array([[
        # 8 raw features (no num_previous_invoices in risk model)
        amount, overdue, credit, avg_dtp, terms,
        num_late, industry_code, total_overdue,
        # 9 engineered features
        overdue_ratio, late_payment_rate, log_amount, log_overdue_ar,
        credit_norm, overdue_band, amount_tier, credit_x_overdue, log_stress,
    ]])


def _heuristic_risk(data: dict) -> dict:
    overdue = float(data.get("days_overdue", 0))
    credit = float(data.get("customer_credit_score", 650))
    late = float(data.get("num_late_payments", 0))
    score = (overdue / 90) * 0.5 + (late / 10) * 0.3
    score += max(0.0, (650 - credit) / 650) * 0.2
    score = min(1.0, max(0.0, score))
    label = "High" if score >= 0.55 else ("Medium" if score >= 0.28 else "Low")
    return {
        "risk_label": label,
        "risk_score": round(score, 4),
        "confidence": 0.70,
        "model_version": "heuristic-fallback-v1",
    }


def classify(data: dict) -> dict:
    """Return risk label, risk score (0–1), and confidence. ML first, then heuristic."""
    features = build_features(data)

    if _model is None or _scaler is None:
        return _heuristic_risk(data)

    try:
        scaled = _scaler.transform(features)
        proba = _model.predict_proba(scaled)[0]
        class_idx = int(np.argmax(proba))
        confidence = float(proba[class_idx])
        risk_score = float(proba[2] * 1.0 + proba[1] * 0.5)
        drivers = top_feature_drivers(
            _model,
            _scaler,
            features,
            [
                "invoice_amount",
                "days_overdue",
                "customer_credit_score",
                "customer_avg_days_to_pay",
                "payment_terms",
                "num_late_payments",
                "industry_encoded",
                "customer_total_overdue",
                "overdue_ratio",
                "late_payment_rate",
                "log_amount",
                "log_overdue_ar",
                "credit_norm",
                "overdue_band",
                "amount_tier",
                "credit_x_overdue",
                "log_stress",
            ],
            top_n=5,
            class_index=class_idx,
            display_names=FEATURE_LABELS,
        )
        return {
            "risk_label": LABEL_MAP[class_idx],
            "risk_score": round(min(1.0, risk_score), 4),
            "confidence": round(confidence, 4),
            "model_version": "xgboost-v1-inr" if _USE_XGB_RISK else "lgbm-v2-inr",
            "feature_drivers": drivers,
            "explanation": summarize_drivers(drivers, f"{LABEL_MAP[class_idx]} risk classification"),
        }
    except Exception:
        return _heuristic_risk(data)
