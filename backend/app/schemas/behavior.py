"""Pydantic schemas for the Payment Behavior Analysis engine."""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.explainability import FeatureDriver


class PaymentBehaviorRequest(BaseModel):
    """Historical payment personality features for a borrower/customer."""

    customer_id: str
    customer_name: str

    # Historical payment metrics
    historical_on_time_ratio: float = Field(..., ge=0, le=1, description="Ratio of invoices paid on-time")
    avg_delay_days: float = Field(..., ge=0, description="Average days delayed beyond due date")
    repayment_consistency: float = Field(..., ge=0, le=1, description="Consistency score — variance of pay days")
    partial_payment_frequency: float = Field(..., ge=0, le=1, description="% of invoices paid partially")
    prior_delayed_invoice_count: int = Field(..., ge=0)
    payment_after_followup_count: int = Field(..., ge=0, description="Payments that only came after follow-up")
    total_invoices: int = Field(..., ge=1)

    # Behavioral signals
    deterioration_trend: float = Field(
        default=0.0,
        ge=-1,
        le=1,
        description="Positive = getting worse, Negative = improving",
    )
    invoice_acknowledgement_behavior: str = Field(
        default="normal",
        description="normal | delayed | ignored | disputed",
    )
    transaction_success_failure_pattern: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Ratio of failed/bounced transactions",
    )


class PaymentBehaviorResponse(BaseModel):
    """Classified payment personality profile for a borrower."""

    customer_id: str
    customer_name: str

    # Classification
    behavior_type: str
    """
    Possible values:
    - "Consistent Payer"
    - "Occasional Late Payer"
    - "Chronic Delayed Payer"
    - "Partial Payment Payer"
    - "Reminder Driven Payer"
    - "High Risk Defaulter"
    """

    # Key metrics
    on_time_ratio: float  # percentage 0–100
    avg_delay_days: float
    trend: str  # "Improving" | "Stable" | "Worsening"
    payment_style: str  # e.g. "Partial + Reminder Driven"

    # Risk signal
    behavior_risk_score: float = Field(..., ge=0, le=100)
    followup_dependency: bool  # True if mostly pays after follow-up
    nach_recommended: bool  # True if NACH/auto-debit is advisable

    # Summary
    behavior_summary: str
    model_version: str = "behavior-rule-v1"
    prediction_source: str = "ml"  # "ml" | "ml+llm" | "rule-based"
    llm_refined: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None
    feature_drivers: list[FeatureDriver] = Field(default_factory=list)
