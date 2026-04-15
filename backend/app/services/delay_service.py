"""
Enhanced Delay Prediction Service.

Consumes payment behavior profile + invoice context to produce an enriched
delay prediction with risk score, risk tier, and human-readable top drivers.
"""

import logging

import httpx

from app.core.config import get_settings
from app.schemas.delay import DelayDriver, DelayPredictionRequest, DelayPredictionResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class DelayService:
    def __init__(self) -> None:
        self.ml_base = settings.ML_SERVICE_URL
        self.timeout = 10.0

    async def predict(self, request: DelayPredictionRequest) -> DelayPredictionResponse:
        """Call ML service; fall back to enriched rule engine."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/predict/delay",
                    json=request.model_dump(),
                )
                resp.raise_for_status()
                return DelayPredictionResponse(**resp.json())
        except Exception as exc:
            logger.warning("ML delay service unavailable (%s) — using rule engine", exc)
            return self._rule_based_delay(request)

    def _rule_based_delay(self, req: DelayPredictionRequest) -> DelayPredictionResponse:
        """
        Enriched rule-based delay prediction.

        Incorporates behavior profile signals on top of invoice features.
        """
        # Base probability from invoice context
        overdue_factor = min(1.0, req.days_overdue / 90)
        credit_factor = max(0.0, (700 - req.customer_credit_score) / 400)
        late_factor = min(1.0, req.num_late_payments / 10)
        overdue_ar_factor = min(1.0, req.customer_total_overdue / 500_000)

        # Behavior enrichment
        behavior_factor = 0.0
        if req.on_time_ratio is not None:
            behavior_factor += (100 - req.on_time_ratio) / 100 * 0.25
        if req.behavior_risk_score is not None:
            behavior_factor += (req.behavior_risk_score / 100) * 0.15
        if req.deterioration_trend is not None and req.deterioration_trend > 0:
            behavior_factor += req.deterioration_trend * 0.10
        if req.followup_dependency:
            behavior_factor += 0.10

        # Amount relative to customer average
        amount_factor = 0.0
        if req.customer_avg_invoice_amount and req.customer_avg_invoice_amount > 0:
            ratio = req.invoice_amount / req.customer_avg_invoice_amount
            if ratio > 2.0:
                amount_factor = min(0.15, (ratio - 1) * 0.05)

        delay_prob = (
            overdue_factor * 0.30
            + credit_factor * 0.15
            + late_factor * 0.15
            + overdue_ar_factor * 0.05
            + behavior_factor
            + amount_factor
        )
        delay_prob = round(min(0.98, max(0.02, delay_prob)), 4)

        risk_score = int(delay_prob * 100)

        if risk_score >= 65:
            risk_tier = "High"
        elif risk_score >= 35:
            risk_tier = "Medium"
        else:
            risk_tier = "Low"

        # Build top drivers
        driver_candidates: list[tuple[float, DelayDriver, str]] = []

        if req.days_overdue > 0:
            w = min(0.4, req.days_overdue / 90)
            driver_candidates.append((w, DelayDriver(
                driver=f"{req.days_overdue} days past due date",
                impact="high" if req.days_overdue > 30 else "medium",
                direction="increases_risk",
            ), f"{req.days_overdue} days already overdue"))

        if req.num_late_payments >= 3:
            w = req.num_late_payments / 10
            driver_candidates.append((w, DelayDriver(
                driver=f"{req.num_late_payments} prior late payments",
                impact="high" if req.num_late_payments > 5 else "medium",
                direction="increases_risk",
            ), f"{req.num_late_payments} prior delays"))

        if req.customer_credit_score < 600:
            w = (700 - req.customer_credit_score) / 400
            driver_candidates.append((w, DelayDriver(
                driver=f"Low credit score ({req.customer_credit_score})",
                impact="high",
                direction="increases_risk",
            ), f"Credit score {req.customer_credit_score} below threshold"))

        if req.behavior_type and "Chronic" in req.behavior_type:
            driver_candidates.append((0.3, DelayDriver(
                driver="Customer classified as Chronic Delayed Payer",
                impact="high",
                direction="increases_risk",
            ), "Chronic delayed payer behavior pattern"))

        if req.behavior_type and "Reminder" in req.behavior_type:
            driver_candidates.append((0.25, DelayDriver(
                driver="Customer requires follow-up before paying",
                impact="medium",
                direction="increases_risk",
            ), "Reminder-driven payment pattern"))

        if amount_factor > 0.05:
            ratio = req.invoice_amount / req.customer_avg_invoice_amount
            driver_candidates.append((amount_factor, DelayDriver(
                driver=f"Invoice is {ratio:.1f}x customer average amount",
                impact="medium",
                direction="increases_risk",
            ), f"Invoice {ratio:.1f}x avg amount"))

        if req.customer_credit_score >= 720 and req.num_late_payments == 0:
            driver_candidates.append((-0.15, DelayDriver(
                driver="Strong credit profile",
                impact="medium",
                direction="decreases_risk",
            ), "Strong credit history"))

        if req.deterioration_trend is not None and req.deterioration_trend > 0.2:
            driver_candidates.append((0.2, DelayDriver(
                driver="Deteriorating payment trend detected",
                impact="medium",
                direction="increases_risk",
            ), "Worsening payment trend"))

        # Sort by weight descending, take top 5
        driver_candidates.sort(key=lambda x: abs(x[0]), reverse=True)
        top_5 = driver_candidates[:5]

        detailed_drivers = [d[1] for d in top_5]
        top_driver_strings = [d[2] for d in top_5]

        return DelayPredictionResponse(
            invoice_id=req.invoice_id,
            delay_probability=delay_prob,
            risk_score=risk_score,
            risk_tier=risk_tier,
            top_drivers=top_driver_strings,
            detailed_drivers=detailed_drivers,
            model_version="rule-engine-v2",
        )
