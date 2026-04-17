"""
Payment behavior inference — XGBoost multiclass (6 classes).
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from explainability.model_driver_explainer import summarize_drivers, top_feature_drivers

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"
MODEL_NAME = "behavior_classifier_xgb"

BEHAVIOR_CLASSES = [
    "Consistent Payer",
    "Occasional Late Payer",
    "Reminder Driven Payer",
    "Partial Payment Payer",
    "Chronic Delayed Payer",
    "High Risk Defaulter",
]

FEATURE_ORDER = [
    "historical_on_time_ratio",
    "avg_delay_days",
    "repayment_consistency",
    "partial_payment_frequency",
    "prior_delayed_invoice_count",
    "payment_after_followup_count",
    "total_invoices",
    "deterioration_trend",
    "transaction_success_failure_pattern",
    "invoice_acknowledgement_encoded",
]

ACK_MAP = {
    "normal": 0,
    "delayed": 1,
    "ignored": 2,
    "disputed": 3,
    # Backward-compatible aliases for older synthetic rows / payloads
    "slow": 1,
    "unresponsive": 2,
}
FEATURE_LABELS = {
    "historical_on_time_ratio": "Historical On-Time Ratio",
    "avg_delay_days": "Average Delay Days",
    "repayment_consistency": "Repayment Consistency",
    "partial_payment_frequency": "Partial Payment Frequency",
    "prior_delayed_invoice_count": "Prior Delayed Invoice Count",
    "payment_after_followup_count": "Payments After Follow-Up",
    "total_invoices": "Total Invoices",
    "deterioration_trend": "Deterioration Trend",
    "transaction_success_failure_pattern": "Transaction Failure Pattern",
    "invoice_acknowledgement_encoded": "Invoice Acknowledgement Behavior",
}


def _load(name: str):
    path = MODEL_DIR / f"{name}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load(MODEL_NAME)
_scaler = _load(f"{MODEL_NAME}_scaler")


def build_features(data: dict) -> np.ndarray:
    ack = str(data.get("invoice_acknowledgement_behavior", "normal")).lower()
    ack_code = ACK_MAP.get(ack, 0)
    return np.array([[
        float(data.get("historical_on_time_ratio", 0)),
        float(data.get("avg_delay_days", 0)),
        float(data.get("repayment_consistency", 0)),
        float(data.get("partial_payment_frequency", 0)),
        float(data.get("prior_delayed_invoice_count", 0)),
        float(data.get("payment_after_followup_count", 0)),
        float(data.get("total_invoices", 1)),
        float(data.get("deterioration_trend", 0)),
        float(data.get("transaction_success_failure_pattern", 0)),
        float(ack_code),
    ]])


def predict_behavior(data: dict) -> Optional[dict]:
    if _model is None or _scaler is None:
        return None
    try:
        X = build_features(data)
        scaled = _scaler.transform(X)
        proba = _model.predict_proba(scaled)[0]
        idx = int(np.argmax(proba))
        behavior_type = BEHAVIOR_CLASSES[idx]
        confidence = float(proba[idx])
        drivers = top_feature_drivers(
            _model,
            _scaler,
            X,
            FEATURE_ORDER,
            top_n=5,
            class_index=idx,
            display_names=FEATURE_LABELS,
        )
        return {
            "behavior_type": behavior_type,
            "behavior_class_index": idx,
            "confidence": round(confidence, 4),
            "feature_drivers": drivers,
            "explanation": summarize_drivers(drivers, behavior_type),
        }
    except Exception:
        return None
