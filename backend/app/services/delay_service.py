"""
Enhanced Delay Prediction Service.

Consumes payment behavior profile + invoice context to produce an enriched
delay prediction with risk score, risk tier, and human-readable top drivers.
"""

import logging

import httpx

from app.core.config import get_settings
from app.services.llm_refiner import LLMRefiner
from app.services.pipeline_validation import clamp_float, normalize_payment_behavior_type
from app.schemas.delay import DelayDriver, DelayPredictionRequest, DelayPredictionResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class DelayService:
    def __init__(self) -> None:
        self.ml_base = settings.ML_SERVICE_URL
        self.timeout = 10.0
        self.refiner = LLMRefiner()

    # Optional fields that enrich evidence quality
    _OPTIONAL_EVIDENCE_FIELDS = [
        "behavior_type",
        "on_time_ratio",
        "avg_delay_days_historical",
        "behavior_risk_score",
        "deterioration_trend",
        "followup_dependency",
    ]
    # Minimum ML confidence threshold — below this we fall back to rules
    _ML_CONFIDENCE_THRESHOLD = 0.55

    def _compute_evidence(self, request: DelayPredictionRequest) -> tuple[float, list[str]]:
        """Return (evidence_score 0-1, list of missing field names)."""
        missing = [
            f for f in self._OPTIONAL_EVIDENCE_FIELDS
            if getattr(request, f, None) is None
        ]
        score = round(1.0 - len(missing) / len(self._OPTIONAL_EVIDENCE_FIELDS), 2)
        return score, missing

    @staticmethod
    def _estimate_ml_confidence(data: dict, evidence_score: float) -> float:
        raw_conf = clamp_float(data.get("confidence"), 0.0, 1.0)
        if raw_conf is not None:
            return round(raw_conf, 2)
        delay_probability = clamp_float(data.get("delay_probability"), 0.0, 1.0, default=0.5)
        assert delay_probability is not None
        separation = abs(delay_probability - 0.5) * 2.0
        derived = 0.35 + separation * 0.40 + evidence_score * 0.20
        return round(min(0.99, max(0.0, derived)), 2)

    @staticmethod
    def _normalize_request(request: DelayPredictionRequest) -> DelayPredictionRequest:
        behavior_type = normalize_payment_behavior_type(request.behavior_type)
        return request.model_copy(update={"behavior_type": behavior_type})

    @staticmethod
    def _operational_risk_score(
        request: DelayPredictionRequest,
        delay_probability: float,
    ) -> int:
        """
        Convert model delay probability into an operational collections risk score.

        The ML delay model is intentionally trained on pre-outcome-safe features, which
        means current collections urgency signals like DPD should still influence the
        final risk tier seen by collectors and dashboards.
        """
        delay_component = delay_probability * 45.0
        overdue_component = min(max(request.days_overdue, 0) / 90.0, 1.0) * 30.0
        late_rate = min(
            max(request.num_late_payments / max(request.num_previous_invoices, 1), 0.0),
            1.0,
        )
        late_component = late_rate * 10.0
        credit_component = max(0.0, (650 - request.customer_credit_score) / 350.0) * 8.0

        behavior_component = 0.0
        if request.behavior_risk_score is not None:
            behavior_component += min(max(request.behavior_risk_score, 0.0), 100.0) / 100.0 * 12.0
        elif request.behavior_type:
            if "Chronic" in request.behavior_type or "High Risk" in request.behavior_type:
                behavior_component += 10.0
            elif "Reminder" in request.behavior_type or "Partial" in request.behavior_type:
                behavior_component += 6.0
            elif "Occasional" in request.behavior_type:
                behavior_component += 3.0

        exposure_ratio = request.customer_total_overdue / max(request.invoice_amount, 1.0)
        exposure_component = min(max(exposure_ratio, 0.0), 3.0) / 3.0 * 5.0

        score = (
            delay_component
            + overdue_component
            + late_component
            + credit_component
            + behavior_component
            + exposure_component
        )
        return int(round(min(100.0, max(0.0, score))))

    @staticmethod
    def _risk_tier_from_score(risk_score: int) -> str:
        if risk_score >= 65:
            return "High"
        if risk_score >= 35:
            return "Medium"
        return "Low"

    async def predict(
        self,
        request: DelayPredictionRequest,
        *,
        allow_llm_refinement: bool = True,
    ) -> DelayPredictionResponse:
        """
        3-phase pipeline: ML -> LLM refinement -> enriched rule fallback.
        Always attaches evidence_score, confidence, missing_data_indicators, used_fallback.
        """
        request = self._normalize_request(request)
        evidence_score, missing = self._compute_evidence(request)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.ml_base}/predict/delay",
                    json=request.model_dump(),
                )
                resp.raise_for_status()
                data = resp.json()
                ml_confidence = self._estimate_ml_confidence(data, evidence_score)

                result = DelayPredictionResponse(**data)
                result.confidence = ml_confidence
                result.evidence_score = evidence_score
                result.missing_data_indicators = missing
                result.used_fallback = False
                result.prediction_source = "ml"
                result.llm_refined = False
                result.llm_used = False
                result.explanation = data.get("explanation") or (
                    f"Phase 1 ML output ({result.model_version}) generated from invoice + behavior signals."
                )
                calibrated_score = self._operational_risk_score(
                    request,
                    float(result.delay_probability),
                )
                result.risk_score = calibrated_score
                result.risk_tier = self._risk_tier_from_score(calibrated_score)

                if ml_confidence < self._ML_CONFIDENCE_THRESHOLD:
                    logger.info(
                        "ML confidence %.2f below threshold %.2f — falling back to rules",
                        ml_confidence,
                        self._ML_CONFIDENCE_THRESHOLD,
                    )
                    return self._rule_based_delay(
                        request,
                        evidence_score,
                        missing,
                        explanation=(
                            "Phase 3 fallback: ML delay prediction confidence was below threshold, "
                            "so bounded rule-engine scoring was used instead."
                        ),
                    )

                if allow_llm_refinement:
                    refined = await self.refiner.refine_delay(
                        {
                            "model_input": request.model_dump(),
                            "ml_output": result.model_dump(),
                        }
                    )
                    if refined:
                        result.delay_probability = refined["delay_probability"]
                        calibrated_score = self._operational_risk_score(
                            request,
                            float(result.delay_probability),
                        )
                        result.risk_score = calibrated_score
                        result.risk_tier = self._risk_tier_from_score(calibrated_score)
                        if refined["top_drivers"]:
                            result.top_drivers = refined["top_drivers"]
                        result.confidence = max(result.confidence, refined["confidence"])
                        result.model_version = f"{result.model_version}+gpt-refiner-v1"
                        result.prediction_source = "ml+llm"
                        result.llm_refined = True
                        result.llm_used = True
                        result.used_fallback = False
                        result.explanation = refined["explanation"]
                        return result

                return result

        except Exception as exc:
            logger.warning("ML delay pipeline failed (%s) — using rule engine", exc)
            return self._rule_based_delay(request, evidence_score, missing)

    def _rule_based_delay(
        self,
        req: DelayPredictionRequest,
        evidence_score: float = 0.5,
        missing: list[str] | None = None,
        *,
        explanation: str | None = None,
    ) -> DelayPredictionResponse:
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

        rule_confidence = round(0.45 + evidence_score * 0.20, 2)

        return DelayPredictionResponse(
            invoice_id=req.invoice_id,
            delay_probability=delay_prob,
            risk_score=risk_score,
            risk_tier=risk_tier,
            top_drivers=top_driver_strings,
            detailed_drivers=detailed_drivers,
            model_version="rule-engine-v2",
            confidence=rule_confidence,
            evidence_score=evidence_score,
            missing_data_indicators=missing or [],
            used_fallback=True,
            prediction_source="rule-based",
            llm_refined=False,
            llm_used=False,
            explanation=explanation or "Phase 3 fallback: rule-engine delay score from DPD, behavior signals, exposure, and credit stress.",
        )
