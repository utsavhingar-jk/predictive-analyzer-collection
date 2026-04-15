"""Pydantic schemas for the What-If scenario simulation engine."""

from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    """Levers the user can adjust in the scenario simulator."""

    recovery_improvement_pct: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="% increase in collection efficiency",
    )
    discount_pct: float = Field(
        default=0.0,
        ge=0,
        le=50,
        description="Early-pay discount offered to customers (%)",
    )
    delay_followup_days: int = Field(
        default=0,
        ge=-30,
        le=30,
        description="Shift follow-up timing by N days (negative = earlier)",
    )


class WhatIfResponse(BaseModel):
    """Projected impact of the scenario on key AR metrics."""

    predicted_recovery_pct: float  # % of outstanding recovered
    cashflow_shift: float  # $ change in 30-day inflow
    dso_shift: float  # change in predicted DSO (days)
    baseline_recovery_pct: float
    baseline_cashflow: float
    baseline_dso: float
    scenario_summary: str  # human-readable summary of the scenario
