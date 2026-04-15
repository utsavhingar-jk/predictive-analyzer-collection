"""Pydantic schemas for the enhanced Delay Prediction engine."""

from typing import Optional
from pydantic import BaseModel, Field


class DelayPredictionRequest(BaseModel):
    """
    Enriched input that combines invoice context, borrower context,
    and the payment behavior profile output.
    """

    invoice_id: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)
    payment_terms: int = Field(default=30, ge=0)
    customer_avg_invoice_amount: float = Field(default=0.0, ge=0)

    # Borrower context
    customer_credit_score: int = Field(..., ge=300, le=850)
    customer_avg_days_to_pay: float = Field(..., ge=0)
    num_late_payments: int = Field(default=0, ge=0)
    customer_total_overdue: float = 0.0

    # From behavior engine output
    behavior_type: Optional[str] = None
    on_time_ratio: Optional[float] = Field(default=None, ge=0, le=100)
    avg_delay_days_historical: Optional[float] = Field(default=None, ge=0)
    behavior_risk_score: Optional[float] = Field(default=None, ge=0, le=100)
    deterioration_trend: Optional[float] = Field(default=None, ge=-1, le=1)
    followup_dependency: Optional[bool] = None


class DelayDriver(BaseModel):
    """A single human-readable explanation for the delay prediction."""

    driver: str
    impact: str  # "high" | "medium" | "low"
    direction: str  # "increases_risk" | "decreases_risk"


class DelayPredictionResponse(BaseModel):
    """Enhanced delay prediction output with risk tier and top drivers."""

    invoice_id: str
    delay_probability: float = Field(..., ge=0, le=1)
    risk_score: int = Field(..., ge=0, le=100)  # 0–100 integer score
    risk_tier: str  # "High" | "Medium" | "Low"
    top_drivers: list[str]  # human-readable driver strings
    detailed_drivers: list[DelayDriver]
    model_version: str = "delay-v2"
