"""
Delay probability inference — XGBoost regressor on the same 18 features as payment.

Maps DelayFeatures (API) onto invoice-style keys expected by payment_predictor.build_features.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers
from inference.payment_predictor import build_features as build_payment_features
from inference.payment_predictor import FEATURE_LABELS, FEATURE_ORDER

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
MODEL_NAME = "delay_probability_xgb"


def _load(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load(MODEL_NAME)
_scaler = _load(f"{MODEL_NAME}_scaler")


def _to_payment_dict(data: dict) -> dict:
    """Normalize DelayFeatures → keys for build_payment_features."""
    industry = data.get("industry", "unknown")
    if industry is None:
        industry = "unknown"
    return {
        "invoice_amount": float(data.get("invoice_amount") or data.get("customer_avg_invoice_amount") or 0),
        "days_overdue": int(data.get("days_overdue", 0)),
        "customer_credit_score": int(data.get("customer_credit_score", 650)),
        "customer_avg_days_to_pay": float(data.get("customer_avg_days_to_pay", 30)),
        "payment_terms": int(data.get("payment_terms", 30)),
        "num_previous_invoices": int(data.get("num_previous_invoices", 10)),
        "num_late_payments": int(data.get("num_late_payments", 0)),
        "industry": industry,
        "customer_total_overdue": float(data.get("customer_total_overdue", 0)),
    }


def predict_delay(data: dict) -> Optional[dict]:
    """
    Return delay_probability in [0.02, 0.98] or None if model missing or inference fails.
    """
    if _model is None or _scaler is None:
        return None
    try:
        payload = _to_payment_dict(data)
        X = build_payment_features(payload)
        scaled = _scaler.transform(X)
        raw = float(_model.predict(scaled)[0])
        drivers = top_feature_drivers(
            _model,
            _scaler,
            X,
            FEATURE_ORDER,
            top_n=5,
            display_names=FEATURE_LABELS,
        )
        return {
            "delay_probability": float(np.clip(raw, 0.02, 0.98)),
            "feature_drivers": drivers,
            "explanation": summarize_drivers(drivers, "delay probability"),
        }
    except Exception:
        return None
