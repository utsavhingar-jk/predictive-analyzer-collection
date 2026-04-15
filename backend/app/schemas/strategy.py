"""Pydantic schemas for the Collection Strategy Optimization engine."""

from typing import Optional
from pydantic import BaseModel, Field


class StrategyRequest(BaseModel):
    """All signals needed to compute an optimised collection strategy."""

    invoice_id: str
    customer_name: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)

    # From delay prediction
    delay_probability: float = Field(..., ge=0, le=1)
    risk_tier: str  # "High" | "Medium" | "Low"

    # Business signals
    urgency_override: Optional[str] = None  # "Critical" | "High" | "Medium" | "Low"
    recoverability_score: float = Field(default=0.7, ge=0, le=1)
    nach_applicable: bool = False
    borrower_type: str = "corporate"  # "corporate" | "sme" | "individual"
    automation_feasible: bool = True

    # From behavior engine
    behavior_type: Optional[str] = None
    followup_dependency: Optional[bool] = None


class StrategyResponse(BaseModel):
    """Optimised collection strategy with priority ranking."""

    invoice_id: str
    priority_score: int = Field(..., ge=0, le=100)
    priority_rank: Optional[int] = None  # rank within portfolio (1 = highest priority)
    recommended_action: str
    urgency: str  # "Critical" | "High" | "Medium" | "Low"
    channel: str  # "Call" | "Email" | "Legal" | "NACH" | "Field Visit" | "Anchor Escalation"
    reason: str
    automation_flag: bool
    next_action_in_hours: int  # SLA for next touch point
