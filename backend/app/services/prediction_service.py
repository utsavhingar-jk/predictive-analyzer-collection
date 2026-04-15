"""
Prediction service — delegates payment and risk predictions to the ML service.

In production this hits the ml-service REST API. When the ML service is
unavailable it falls back to heuristic mock predictions so the backend
stays usable during development without a running ML service.
"""

import logging
from typing import Optional

import httpx

from app.core.config import get_settings
from app.schemas.prediction import (
    PaymentPredictionRequest,
    PaymentPredictionResponse,
    RiskClassificationRequest,
    RiskClassificationResponse,
    ShapExplanationResponse,
    ShapFeature,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class PredictionService:
    def __init__(self) -> None:
        self.ml_base = settings.ML_SERVICE_URL
        self.timeout = 10.0

    # ─── Payment Prediction ───────────────────────────────────────────────────

    async def predict_payment(
        self, request: PaymentPredictionRequest
    ) -> PaymentPredictionResponse:
        """Call ML service for payment probability; fall back to heuristics."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/predict/payment",
                    json=request.model_dump(),
                )
                resp.raise_for_status()
                return PaymentPredictionResponse(**resp.json())
        except Exception as exc:
            logger.warning("ML service unavailable (%s) — using heuristic", exc)
            return self._heuristic_payment(request)

    def _heuristic_payment(
        self, req: PaymentPredictionRequest
    ) -> PaymentPredictionResponse:
        """Rule-based fallback when ML service is unreachable."""
        base = max(0.0, 1.0 - (req.days_overdue / 90))
        credit_factor = req.customer_credit_score / 850
        late_penalty = req.num_late_payments * 0.05

        p7 = max(0.0, min(1.0, base * credit_factor * 0.5 - late_penalty))
        p15 = max(0.0, min(1.0, base * credit_factor * 0.7 - late_penalty))
        p30 = max(0.0, min(1.0, base * credit_factor * 0.9 - late_penalty))

        return PaymentPredictionResponse(
            invoice_id=req.invoice_id,
            pay_7_days=round(p7, 4),
            pay_15_days=round(p15, 4),
            pay_30_days=round(p30, 4),
            model_version="heuristic-fallback",
        )

    # ─── Risk Classification ──────────────────────────────────────────────────

    async def classify_risk(
        self, request: RiskClassificationRequest
    ) -> RiskClassificationResponse:
        """Call ML service for risk classification; fall back to heuristics."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/predict/risk",
                    json=request.model_dump(),
                )
                resp.raise_for_status()
                return RiskClassificationResponse(**resp.json())
        except Exception as exc:
            logger.warning("ML service unavailable (%s) — using heuristic", exc)
            return self._heuristic_risk(request)

    def _heuristic_risk(
        self, req: RiskClassificationRequest
    ) -> RiskClassificationResponse:
        score = (req.days_overdue / 90) * 0.5 + (req.num_late_payments / 10) * 0.3
        score += max(0.0, (650 - req.customer_credit_score) / 650) * 0.2
        score = min(1.0, max(0.0, score))

        if score >= 0.65:
            label = "High"
        elif score >= 0.35:
            label = "Medium"
        else:
            label = "Low"

        return RiskClassificationResponse(
            invoice_id=req.invoice_id,
            risk_label=label,
            risk_score=round(score, 4),
            confidence=0.75,
            model_version="heuristic-fallback",
        )

    # ─── SHAP Explainability ──────────────────────────────────────────────────

    async def explain(self, invoice_id: str, features: dict) -> ShapExplanationResponse:
        """Fetch SHAP explanation from ML service; return mock on failure."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/explain",
                    json={"invoice_id": invoice_id, "features": features},
                )
                resp.raise_for_status()
                return ShapExplanationResponse(**resp.json())
        except Exception as exc:
            logger.warning("SHAP service unavailable (%s) — using mock", exc)
            return self._mock_shap(invoice_id)

    def _mock_shap(self, invoice_id: str) -> ShapExplanationResponse:
        mock_features = [
            ShapFeature(
                feature_name="days_overdue",
                feature_value=45.0,
                shap_value=0.32,
                impact="negative",
            ),
            ShapFeature(
                feature_name="customer_credit_score",
                feature_value=620.0,
                shap_value=-0.18,
                impact="positive",
            ),
            ShapFeature(
                feature_name="num_late_payments",
                feature_value=3.0,
                shap_value=0.22,
                impact="negative",
            ),
            ShapFeature(
                feature_name="invoice_amount",
                feature_value=15000.0,
                shap_value=0.08,
                impact="negative",
            ),
            ShapFeature(
                feature_name="avg_days_to_pay",
                feature_value=38.0,
                shap_value=-0.05,
                impact="positive",
            ),
        ]
        return ShapExplanationResponse(
            invoice_id=invoice_id,
            top_features=mock_features,
            base_value=0.45,
            prediction_value=0.72,
        )
