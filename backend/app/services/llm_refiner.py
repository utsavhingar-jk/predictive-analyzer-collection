"""LLM refinement layer for hybrid 3-phase prediction pipeline."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.core.config import get_settings
from app.services.pipeline_validation import (
    clamp_float,
    clamp_int,
    coerce_bool,
    normalize_payment_behavior_type,
    normalize_risk_tier,
    normalize_trend,
    sanitize_top_drivers,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class LLMRefiner:
    """Refines ML predictions using request + ML output context.

    Implemented as a singleton — all services share one instance so only
    a single pair of AsyncOpenAI / OpenAI clients is ever created.
    """

    _instance: "LLMRefiner | None" = None

    def __new__(cls) -> "LLMRefiner":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialised = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialised", False):
            return
        self.model = settings.OPENAI_MODEL
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.sync_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self._initialised = True

    @property
    def enabled(self) -> bool:
        return self.client is not None

    async def _json_completion(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.client:
            return None
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
            content = (response.choices[0].message.content or "{}").strip()
            return json.loads(content)
        except Exception as exc:
            logger.warning("LLM refinement failed: %s", exc)
            return None

    def _json_completion_sync(self, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.sync_client:
            return None
        try:
            response = self.sync_client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
            content = (response.choices[0].message.content or "{}").strip()
            return json.loads(content)
        except Exception as exc:
            logger.warning("LLM sync refinement failed: %s", exc)
            return None

    async def refine_payment(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = await self._json_completion(
            (
                "You refine invoice payment probability predictions. "
                "Given model_input and ml_output, return improved values as JSON with keys: "
                "pay_7_days, pay_15_days, pay_30_days, explanation. "
                "Keep all probabilities in [0,1] and enforce pay_7_days <= pay_15_days <= pay_30_days."
            ),
            payload,
        )
        if not result:
            return None
        p7 = clamp_float(result.get("pay_7_days", payload["ml_output"]["pay_7_days"]), 0.0, 1.0)
        p15 = clamp_float(result.get("pay_15_days", payload["ml_output"]["pay_15_days"]), 0.0, 1.0)
        p30 = clamp_float(result.get("pay_30_days", payload["ml_output"]["pay_30_days"]), 0.0, 1.0)
        if p7 is None or p15 is None or p30 is None:
            return None
        p15 = max(p7, p15)
        p30 = max(p15, p30)
        return {
            "pay_7_days": round(p7, 4),
            "pay_15_days": round(p15, 4),
            "pay_30_days": round(p30, 4),
            "explanation": str(result.get("explanation", "LLM refined using ML output + invoice context.")),
        }

    async def refine_risk(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = await self._json_completion(
            (
                "You refine invoice risk classification. "
                "Given model_input and ml_output, return JSON keys: risk_score, risk_label, confidence, explanation. "
                "risk_score/confidence must be in [0,1]. risk_label must be High, Medium, or Low."
            ),
            payload,
        )
        if not result:
            return None
        score = clamp_float(result.get("risk_score", payload["ml_output"]["risk_score"]), 0.0, 1.0)
        if score is None:
            return None
        label = normalize_risk_tier(result.get("risk_label", payload["ml_output"]["risk_label"]))
        if label not in {"High", "Medium", "Low"}:
            label = "High" if score >= 0.67 else "Medium" if score >= 0.40 else "Low"
        confidence = clamp_float(
            result.get("confidence", payload["ml_output"].get("confidence", 0.75)),
            0.0,
            1.0,
        )
        if confidence is None:
            return None
        return {
            "risk_score": round(score, 4),
            "risk_label": label,
            "confidence": round(confidence, 4),
            "explanation": str(result.get("explanation", "LLM refined using ML output + borrower context.")),
        }

    async def refine_delay(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = await self._json_completion(
            (
                "You refine delay predictions. "
                "Given model_input and ml_output, return JSON keys: delay_probability, risk_score, risk_tier, "
                "top_drivers, explanation, confidence. "
                "delay_probability/confidence in [0,1], risk_score in [0,100], risk_tier in High/Medium/Low, "
                "top_drivers as a list of concise strings."
            ),
            payload,
        )
        if not result:
            return None
        delay_probability = clamp_float(
            result.get("delay_probability", payload["ml_output"]["delay_probability"]),
            0.0,
            1.0,
        )
        if delay_probability is None:
            return None
        risk_score = clamp_int(result.get("risk_score", delay_probability * 100), 0, 100)
        if risk_score is None:
            return None
        risk_tier = normalize_risk_tier(
            result.get("risk_tier", payload["ml_output"]["risk_tier"])
        )
        if risk_tier not in {"High", "Medium", "Low"}:
            risk_tier = "High" if risk_score >= 65 else "Medium" if risk_score >= 35 else "Low"
        top_drivers = sanitize_top_drivers(
            result.get("top_drivers", payload["ml_output"].get("top_drivers", []))
        )
        confidence = clamp_float(
            result.get("confidence", payload["ml_output"].get("confidence", 0.75)),
            0.0,
            1.0,
        )
        if confidence is None:
            return None
        return {
            "delay_probability": round(delay_probability, 4),
            "risk_score": risk_score,
            "risk_tier": risk_tier,
            "top_drivers": top_drivers,
            "confidence": round(confidence, 4),
            "explanation": str(result.get("explanation", "LLM refined using ML output + behavior context.")),
        }

    async def refine_behavior(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = await self._json_completion(
            (
                "You refine borrower payment behavior classification. "
                "Given model_input and ml_output, return JSON keys: behavior_type, trend, behavior_risk_score, "
                "followup_dependency, nach_recommended, behavior_summary, explanation. "
                "behavior_type must be one of: Consistent Payer, Occasional Late Payer, Reminder Driven Payer, "
                "Partial Payment Payer, Chronic Delayed Payer, High Risk Defaulter. "
                "behavior_risk_score in [0,100]. trend must be Improving, Stable, or Worsening."
            ),
            payload,
        )
        if not result:
            return None
        behavior_type = normalize_payment_behavior_type(
            result.get("behavior_type", payload["ml_output"]["behavior_type"])
        )
        if behavior_type is None:
            return None
        trend = normalize_trend(result.get("trend", payload["ml_output"].get("trend", "Stable")))
        if trend is None:
            return None
        behavior_risk_score = clamp_float(
            result.get("behavior_risk_score", payload["ml_output"]["behavior_risk_score"]),
            0.0,
            100.0,
        )
        if behavior_risk_score is None:
            return None
        return {
            "behavior_type": behavior_type,
            "trend": trend,
            "behavior_risk_score": round(behavior_risk_score, 1),
            "followup_dependency": coerce_bool(
                result.get(
                    "followup_dependency",
                    payload["ml_output"].get("followup_dependency", False),
                )
            ),
            "nach_recommended": coerce_bool(
                result.get("nach_recommended", payload["ml_output"].get("nach_recommended", False))
            ),
            "behavior_summary": str(result.get("behavior_summary", payload["ml_output"].get("behavior_summary", "LLM refined behavior profile."))),
            "explanation": str(result.get("explanation", "LLM refined behavior using ML output + business context.")),
        }

    def refine_borrower_sync(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = self._json_completion_sync(
            (
                "You refine borrower-level risk predictions. "
                "Given model_input and ml_output, return JSON keys: "
                "borrower_risk_score, borrower_risk_tier, weighted_delay_probability, "
                "expected_recovery_rate, escalation_recommended, relationship_action, borrower_summary, explanation. "
                "borrower_risk_score in [0,100], weighted_delay_probability and expected_recovery_rate in [0,1], "
                "borrower_risk_tier in High/Medium/Low."
            ),
            payload,
        )
        if not result:
            return None

        risk_score = clamp_int(result.get("borrower_risk_score", 50), 0, 100)
        if risk_score is None:
            return None
        risk_tier = normalize_risk_tier(result.get("borrower_risk_tier", "Medium"))
        if risk_tier not in {"High", "Medium", "Low"}:
            risk_tier = "High" if risk_score >= 65 else "Medium" if risk_score >= 35 else "Low"
        weighted_delay_probability = clamp_float(
            result.get("weighted_delay_probability", 0.5),
            0.0,
            1.0,
        )
        expected_recovery_rate = clamp_float(
            result.get("expected_recovery_rate", 0.5),
            0.0,
            1.0,
        )
        if weighted_delay_probability is None or expected_recovery_rate is None:
            return None

        return {
            "borrower_risk_score": risk_score,
            "borrower_risk_tier": risk_tier,
            "weighted_delay_probability": round(weighted_delay_probability, 4),
            "expected_recovery_rate": round(expected_recovery_rate, 4),
            "escalation_recommended": coerce_bool(result.get("escalation_recommended", False)),
            "relationship_action": str(result.get("relationship_action", "Follow-up Email + Call")),
            "borrower_summary": str(result.get("borrower_summary", payload["ml_output"].get("borrower_summary", "LLM refined borrower summary."))),
            "explanation": str(result.get("explanation", "LLM refined borrower prediction using ML output + borrower exposure context.")),
        }
