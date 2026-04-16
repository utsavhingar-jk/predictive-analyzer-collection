"""Shared risk scoring helpers (amount + DPD combined)."""

from __future__ import annotations

from typing import Iterable


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def percentile(values: Iterable[float], q: float) -> float:
    nums = sorted(float(v) for v in values if v is not None)
    if not nums:
        return 1.0
    if len(nums) == 1:
        return nums[0]
    q = _clamp(q, 0.0, 1.0)
    pos = (len(nums) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(nums) - 1)
    frac = pos - lo
    return nums[lo] * (1.0 - frac) + nums[hi] * frac


def build_amount_reference(amounts: Iterable[float]) -> float:
    # P90 gives stable scaling and avoids tiny invoices dominating.
    return max(percentile(amounts, 0.90), 1.0)


def risk_score(days_overdue: int, amount: float, amount_reference: float) -> float:
    """Return combined risk score in [0, 1] using average(amount, DPD)."""
    dpd_component = _clamp(float(days_overdue) / 90.0)
    amount_component = _clamp(float(amount) / max(float(amount_reference), 1.0))
    return _clamp((dpd_component + amount_component) / 2.0)


def risk_tier_from_score(score: float) -> str:
    if score >= 0.67:
        return "High"
    if score >= 0.40:
        return "Medium"
    return "Low"


def delay_probability_from_score(score: float) -> float:
    # Keep probability in [0.05, 0.95] for downstream stability.
    return _clamp(score, 0.05, 0.95)
