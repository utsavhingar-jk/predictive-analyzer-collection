"""LLM refinement layer for hybrid 3-phase prediction pipeline."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class LLMRefiner:
    """Refines ML predictions using request + ML output context."""

    def __init__(self) -> None:
        self.model = settings.OPENAI_MODEL
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        self.sync_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

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
        p7 = _clamp(float(result.get("pay_7_days", payload["ml_output"]["pay_7_days"])))
        p15 = _clamp(float(result.get("pay_15_days", payload["ml_output"]["pay_15_days"])))
        p30 = _clamp(float(result.get("pay_30_days", payload["ml_output"]["pay_30_days"])))
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
        score = _clamp(float(result.get("risk_score", payload["ml_output"]["risk_score"])))
        label = str(result.get("risk_label", payload["ml_output"]["risk_label"])).title()
        if label not in {"High", "Medium", "Low"}:
            label = "High" if score >= 0.67 else "Medium" if score >= 0.40 else "Low"
        confidence = _clamp(float(result.get("confidence", payload["ml_output"].get("confidence", 0.75))))
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
        delay_probability = _clamp(float(result.get("delay_probability", payload["ml_output"]["delay_probability"])))
        risk_score = int(max(0, min(100, round(float(result.get("risk_score", delay_probability * 100))))))
        risk_tier = str(result.get("risk_tier", payload["ml_output"]["risk_tier"])).title()
        if risk_tier not in {"High", "Medium", "Low"}:
            risk_tier = "High" if risk_score >= 65 else "Medium" if risk_score >= 35 else "Low"
        top_drivers_raw = result.get("top_drivers", payload["ml_output"].get("top_drivers", []))
        top_drivers = [str(x) for x in top_drivers_raw][:5] if isinstance(top_drivers_raw, list) else []
        confidence = _clamp(float(result.get("confidence", payload["ml_output"].get("confidence", 0.75))))
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
                "followup_dependency, nach_recommended, behavior_summary. "
                "behavior_risk_score in [0,100]. trend must be Improving, Stable, or Worsening."
            ),
            payload,
        )
        if not result:
            return None
        trend = str(result.get("trend", payload["ml_output"].get("trend", "Stable"))).title()
        if trend not in {"Improving", "Stable", "Worsening"}:
            trend = "Stable"
        return {
            "behavior_type": str(result.get("behavior_type", payload["ml_output"]["behavior_type"])),
            "trend": trend,
            "behavior_risk_score": round(max(0.0, min(100.0, float(result.get("behavior_risk_score", payload["ml_output"]["behavior_risk_score"])))), 1),
            "followup_dependency": bool(result.get("followup_dependency", payload["ml_output"].get("followup_dependency", False))),
            "nach_recommended": bool(result.get("nach_recommended", payload["ml_output"].get("nach_recommended", False))),
            "behavior_summary": str(result.get("behavior_summary", payload["ml_output"].get("behavior_summary", "LLM refined behavior profile."))),
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

        risk_score = int(max(0, min(100, round(float(result.get("borrower_risk_score", 50))))))
        risk_tier = str(result.get("borrower_risk_tier", "Medium")).title()
        if risk_tier not in {"High", "Medium", "Low"}:
            risk_tier = "High" if risk_score >= 65 else "Medium" if risk_score >= 35 else "Low"

        return {
            "borrower_risk_score": risk_score,
            "borrower_risk_tier": risk_tier,
            "weighted_delay_probability": round(_clamp(float(result.get("weighted_delay_probability", 0.5))), 4),
            "expected_recovery_rate": round(_clamp(float(result.get("expected_recovery_rate", 0.5))), 4),
            "escalation_recommended": bool(result.get("escalation_recommended", False)),
            "relationship_action": str(result.get("relationship_action", "Follow-up Email + Call")),
            "borrower_summary": str(result.get("borrower_summary", payload["ml_output"].get("borrower_summary", "LLM refined borrower summary."))),
            "explanation": str(result.get("explanation", "LLM refined borrower prediction using ML output + borrower exposure context.")),
        }
