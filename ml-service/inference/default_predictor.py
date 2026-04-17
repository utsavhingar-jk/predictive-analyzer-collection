"""
Default probability inference.

Predicts the probability that an invoice remains unpaid after 30 days using
the same pre-outcome-safe feature set as the payment models.
"""

import pickle
from pathlib import Path

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers
from inference.payment_predictor import (
    FEATURE_LABELS,
    FEATURE_ORDER,
    _heuristic_payment_probs,
    build_features,
)

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
MODEL_NAME = "default_model_30d"


def _load(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load(MODEL_NAME)
_scaler = _load(f"{MODEL_NAME}_scaler")


def _risk_tier(probability: float) -> str:
    if probability >= 0.65:
        return "High"
    if probability >= 0.35:
        return "Medium"
    return "Low"


def _heuristic_default(data: dict) -> dict:
    _, _, p30 = _heuristic_payment_probs(data)
    late_rate = min(
        1.0,
        float(data.get("num_late_payments", 0)) / max(float(data.get("num_previous_invoices", 1)), 1.0),
    )
    credit_stress = min(
        1.0,
        max(0.0, (650.0 - float(data.get("customer_credit_score", 650))) / 350.0),
    )
    exposure_stress = min(
        1.0,
        float(data.get("customer_total_overdue", 0.0)) / max(float(data.get("invoice_amount", 1.0)) * 2.0, 1.0),
    )

    probability = (
        max(0.0, 1.0 - p30) * 0.72
        + late_rate * 0.14
        + credit_stress * 0.09
        + exposure_stress * 0.05
    )
    probability = round(min(0.98, max(0.01, probability)), 4)
    return {
        "default_probability": probability,
        "default_risk_tier": _risk_tier(probability),
        "confidence": 0.72,
        "model_version": "heuristic-default-fallback",
        "feature_drivers": [],
        "explanation": (
            "Default fallback used the 30-day non-payment proxy plus late-payment history, "
            "credit stress, and exposure stress."
        ),
    }


def predict_default(data: dict) -> dict:
    """Return default probability in [0,1] plus explainability fields."""
    if _model is None or _scaler is None:
        return _heuristic_default(data)

    try:
        features = build_features(data)
        scaled = _scaler.transform(features)
        proba = _model.predict_proba(scaled)[0]
        probability = float(round(proba[1], 4))
        confidence = float(round(max(proba[0], proba[1]), 4))
        drivers = top_feature_drivers(
            _model,
            _scaler,
            features,
            FEATURE_ORDER,
            top_n=5,
            class_index=0,
            display_names=FEATURE_LABELS,
        )
        return {
            "default_probability": probability,
            "default_risk_tier": _risk_tier(probability),
            "confidence": confidence,
            "model_version": "xgboost-default-v1",
            "feature_drivers": drivers,
            "explanation": summarize_drivers(drivers, "default probability"),
        }
    except Exception:
        return _heuristic_default(data)
