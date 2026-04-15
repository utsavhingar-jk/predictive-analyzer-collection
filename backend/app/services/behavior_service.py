"""
Payment Behavior Analysis Service.

Classifies a borrower's payment personality based on historical payment
patterns. In production this calls the ML service for model-based
classification; falls back to deterministic rules for immediate usability.
"""

import logging

import httpx

from app.core.config import get_settings
from app.schemas.behavior import PaymentBehaviorRequest, PaymentBehaviorResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class BehaviorService:
    def __init__(self) -> None:
        self.ml_base = settings.ML_SERVICE_URL
        self.timeout = 10.0

    async def analyze(self, request: PaymentBehaviorRequest) -> PaymentBehaviorResponse:
        """
        Classify borrower payment behavior.

        Attempts ml-service first; falls back to deterministic rule engine.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/analyze/payment-behavior",
                    json=request.model_dump(),
                )
                resp.raise_for_status()
                return PaymentBehaviorResponse(**resp.json())
        except Exception as exc:
            logger.warning("ML behavior service unavailable (%s) — using rule engine", exc)
            return self._rule_based_classify(request)

    def _rule_based_classify(self, req: PaymentBehaviorRequest) -> PaymentBehaviorResponse:
        """
        Deterministic rule engine for payment behavior classification.

        Scoring matrix:
          - on_time_ratio      → lower = worse
          - avg_delay_days     → higher = worse
          - partial_frequency  → higher = worse
          - followup_count     → higher relative to total = worse
          - deterioration      → positive = worse
          - ack_behavior       → ignored/disputed = worse
        """
        # Normalised risk sub-scores (0–1 each)
        delay_score = min(1.0, req.avg_delay_days / 60)
        late_ratio_score = 1.0 - req.historical_on_time_ratio
        followup_ratio = req.payment_after_followup_count / max(req.total_invoices, 1)
        partial_score = req.partial_payment_frequency
        trend_penalty = max(0.0, req.deterioration_trend)  # only penalise worsening
        ack_penalty = {"ignored": 0.3, "disputed": 0.25, "delayed": 0.1, "normal": 0.0}.get(
            req.invoice_acknowledgement_behavior, 0.0
        )
        failure_score = req.transaction_success_failure_pattern

        # Composite risk score 0–100
        raw = (
            delay_score * 0.25
            + late_ratio_score * 0.20
            + followup_ratio * 0.15
            + partial_score * 0.10
            + trend_penalty * 0.10
            + ack_penalty * 0.10
            + failure_score * 0.10
        )
        behavior_risk_score = round(min(100.0, raw * 100), 1)

        # Trend
        if req.deterioration_trend > 0.2:
            trend = "Worsening"
        elif req.deterioration_trend < -0.1:
            trend = "Improving"
        else:
            trend = "Stable"

        # Classify behavior type
        on_time_pct = req.historical_on_time_ratio * 100

        if on_time_pct >= 85 and req.avg_delay_days < 5:
            behavior_type = "Consistent Payer"
            payment_style = "Prompt + Autonomous"
        elif on_time_pct >= 65 and req.avg_delay_days < 15:
            behavior_type = "Occasional Late Payer"
            payment_style = "Mostly On-Time"
        elif followup_ratio >= 0.5:
            behavior_type = "Reminder Driven Payer"
            payment_style = "Requires Follow-Up"
        elif req.partial_payment_frequency >= 0.4:
            behavior_type = "Partial Payment Payer"
            payment_style = "Partial + Reminder Driven"
        elif on_time_pct < 35 or req.avg_delay_days > 30:
            behavior_type = "Chronic Delayed Payer"
            payment_style = "Chronic Late + High DPD"
        elif behavior_risk_score >= 75:
            behavior_type = "High Risk Defaulter"
            payment_style = "Erratic + Non-Responsive"
        else:
            behavior_type = "Occasional Late Payer"
            payment_style = "Intermittent Delays"

        # NACH recommendation: auto-debit sensible for reminder-driven or partial payers
        nach_recommended = behavior_type in (
            "Reminder Driven Payer",
            "Partial Payment Payer",
            "Chronic Delayed Payer",
        )

        followup_dependency = followup_ratio >= 0.4

        # Human-readable summary
        summary = (
            f"{req.customer_name} is classified as a '{behavior_type}'. "
            f"On-time payment ratio is {on_time_pct:.0f}% with an average delay of "
            f"{req.avg_delay_days:.0f} days. "
            f"Payment trend is {trend.lower()}. "
            f"{'NACH/auto-debit is recommended. ' if nach_recommended else ''}"
            f"Behavior risk score: {behavior_risk_score}/100."
        )

        return PaymentBehaviorResponse(
            customer_id=req.customer_id,
            customer_name=req.customer_name,
            behavior_type=behavior_type,
            on_time_ratio=round(on_time_pct, 1),
            avg_delay_days=round(req.avg_delay_days, 1),
            trend=trend,
            payment_style=payment_style,
            behavior_risk_score=behavior_risk_score,
            followup_dependency=followup_dependency,
            nach_recommended=nach_recommended,
            behavior_summary=summary,
        )
