"""
SHAP Explainability Service.

Uses SHAP TreeExplainer to compute feature-level attributions for
payment probability predictions. Returns top-N features sorted by |SHAP value|.
"""

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import shap

from inference.payment_predictor import build_features

MODEL_DIR = Path(__file__).parent.parent / "serialized_models"

FEATURE_NAMES = [
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


def explain(data: dict, top_n: int = 5) -> dict:
    """
    Compute SHAP values for the 30-day payment model and return
    the top-N most impactful features.
    """
    model = _load_model("payment_model_30d")
    scaler = _load_scaler("payment_model_30d")

    if model is None or scaler is None:
        return _mock_explanation(data, top_n)

    features = build_features(data)
    scaled = scaler.transform(features)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(scaled)

    # For binary XGBoost, shap_values is 2D; take class=1 (payment) values
    if isinstance(shap_values, list):
        sv = shap_values[1][0]
    else:
        sv = shap_values[0]

    raw_features = features[0]

    feature_data = [
        {
            "feature_name": FEATURE_NAMES[i],
            "feature_value": float(raw_features[i]),
            "shap_value": float(sv[i]),
            "impact": "positive" if sv[i] >= 0 else "negative",
        }
        for i in range(len(FEATURE_NAMES))
    ]

    # Sort by absolute SHAP value, take top N
    top_features = sorted(feature_data, key=lambda x: abs(x["shap_value"]), reverse=True)[:top_n]

    base_value = float(explainer.expected_value if not isinstance(explainer.expected_value, list)
                       else explainer.expected_value[1])

    return {
        "top_features": top_features,
        "base_value": round(base_value, 4),
        "prediction_value": round(float(base_value + sum(sv)), 4),
    }


def _mock_explanation(data: dict, top_n: int) -> dict:
    """Return a structured mock explanation when models are not yet trained."""
    return {
        "top_features": [
            {"feature_name": "days_overdue", "feature_value": float(data.get("days_overdue", 30)),
             "shap_value": 0.32, "impact": "negative"},
            {"feature_name": "customer_credit_score", "feature_value": float(data.get("customer_credit_score", 650)),
             "shap_value": -0.18, "impact": "positive"},
            {"feature_name": "num_late_payments", "feature_value": float(data.get("num_late_payments", 2)),
             "shap_value": 0.22, "impact": "negative"},
            {"feature_name": "invoice_amount", "feature_value": float(data.get("invoice_amount", 10000)),
             "shap_value": 0.08, "impact": "negative"},
            {"feature_name": "customer_avg_days_to_pay", "feature_value": float(data.get("customer_avg_days_to_pay", 35)),
             "shap_value": -0.05, "impact": "positive"},
        ][:top_n],
        "base_value": 0.45,
        "prediction_value": 0.72,
    }
