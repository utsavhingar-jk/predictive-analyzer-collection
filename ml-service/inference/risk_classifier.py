"""
Risk Classification Inference Module.

Loads the trained LightGBM classifier and returns risk label + score.
"""

import pickle
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
LABEL_MAP = {0: "Low", 1: "Medium", 2: "High"}

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


def _load_artifact(name: str):
    path = MODEL_DIR / name
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load_artifact("risk_classifier_lgbm.pkl")
_scaler = _load_artifact("risk_classifier_lgbm_scaler.pkl")


def build_features(data: dict) -> np.ndarray:
    amount = float(data.get("invoice_amount", 0))
    overdue = float(data.get("days_overdue", 0))
    terms = float(data.get("payment_terms", 30))
    late = float(data.get("num_late_payments", 0))
    prev = float(data.get("num_previous_invoices", 1))
    total_overdue = float(data.get("customer_total_overdue", 0))
    industry = float(INDUSTRY_MAP.get(str(data.get("industry", "unknown")).lower(), 7))

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
        late,
        industry,
        total_overdue,
        overdue_ratio,
        late_payment_rate,
        log_amount,
        log_overdue_ar,
    ]])


def classify(data: dict) -> dict:
    """Return risk label and risk score (0–1). Falls back to heuristic."""
    features = build_features(data)

    if _model is None or _scaler is None:
        # Heuristic fallback
        overdue = float(data.get("days_overdue", 0))
        credit = float(data.get("customer_credit_score", 650))
        late = float(data.get("num_late_payments", 0))

        score = (overdue / 90) * 0.5 + (late / 10) * 0.3
        score += max(0.0, (650 - credit) / 650) * 0.2
        score = min(1.0, max(0.0, score))

        label = "High" if score >= 0.65 else ("Medium" if score >= 0.35 else "Low")
        return {
            "risk_label": label,
            "risk_score": round(score, 4),
            "confidence": 0.70,
            "model_version": "heuristic-fallback",
        }

    scaled = _scaler.transform(features)
    proba = _model.predict_proba(scaled)[0]  # [p_low, p_medium, p_high]
    class_idx = int(np.argmax(proba))
    confidence = float(proba[class_idx])
    risk_score = float(proba[2] * 1.0 + proba[1] * 0.5)  # weighted severity score

    return {
        "risk_label": LABEL_MAP[class_idx],
        "risk_score": round(min(1.0, risk_score), 4),
        "confidence": round(confidence, 4),
        "model_version": "lgbm-v1",
    }
