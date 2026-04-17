"""Shared validation helpers for hybrid ML + LLM prediction pipelines."""

from __future__ import annotations

from typing import Any, Iterable

ACK_BEHAVIOR_TYPES = (
    "normal",
    "delayed",
    "ignored",
    "disputed",
)

ACK_BEHAVIOR_ALIASES = {
    "normal": "normal",
    "slow": "delayed",
    "delayed": "delayed",
    "ignored": "ignored",
    "unresponsive": "ignored",
    "disputed": "disputed",
}

PAYMENT_BEHAVIOR_TYPES = (
    "Consistent Payer",
    "Occasional Late Payer",
    "Reminder Driven Payer",
    "Partial Payment Payer",
    "Chronic Delayed Payer",
    "High Risk Defaulter",
)

_PAYMENT_BEHAVIOR_ALIASES = {
    "consistent payer": "Consistent Payer",
    "occasional late payer": "Occasional Late Payer",
    "reminder driven payer": "Reminder Driven Payer",
    "partial payment payer": "Partial Payment Payer",
    "chronic delayed payer": "Chronic Delayed Payer",
    "high risk defaulter": "High Risk Defaulter",
}

RISK_TIER_VALUES = ("High", "Medium", "Low")
TREND_VALUES = ("Improving", "Stable", "Worsening")

PAYMENT_STYLE_BY_BEHAVIOR_TYPE = {
    "Consistent Payer": "Prompt + Autonomous",
    "Occasional Late Payer": "Mostly On-Time",
    "Reminder Driven Payer": "Requires Follow-Up",
    "Partial Payment Payer": "Partial + Reminder Driven",
    "Chronic Delayed Payer": "Chronic Late + High DPD",
    "High Risk Defaulter": "Erratic + Non-Responsive",
}


def clamp_float(
    value: Any,
    lower: float,
    upper: float,
    *,
    default: float | None = None,
) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, num))


def clamp_int(
    value: Any,
    lower: int,
    upper: int,
    *,
    default: int | None = None,
) -> int | None:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(lower, min(upper, num))


def coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def normalize_acknowledgement_behavior(value: Any, *, default: str = "normal") -> str:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return ACK_BEHAVIOR_ALIASES.get(normalized, default)


def normalize_trend(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().title()
    return normalized if normalized in TREND_VALUES else None


def normalize_risk_tier(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().title()
    return normalized if normalized in RISK_TIER_VALUES else None


def normalize_payment_behavior_type(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized in PAYMENT_BEHAVIOR_TYPES:
        return normalized
    return _PAYMENT_BEHAVIOR_ALIASES.get(normalized.lower())


def payment_style_for_behavior_type(value: Any, *, default: str = "Intermittent Delays") -> str:
    behavior_type = normalize_payment_behavior_type(value)
    if behavior_type is None:
        return default
    return PAYMENT_STYLE_BY_BEHAVIOR_TYPE.get(behavior_type, default)


def sanitize_top_drivers(value: Any, *, limit: int = 5) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    cleaned: list[str] = []
    for item in value:
        driver = str(item).strip()
        if not driver or driver in cleaned:
            continue
        cleaned.append(driver)
        if len(cleaned) >= limit:
            break
    return cleaned
