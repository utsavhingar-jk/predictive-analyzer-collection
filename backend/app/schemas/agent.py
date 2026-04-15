"""Pydantic schemas for the orchestrated OpenAI Agent analyze-case endpoint."""

from typing import Optional, Union
from pydantic import BaseModel, field_validator

from app.schemas.behavior import PaymentBehaviorResponse
from app.schemas.delay import DelayPredictionResponse
from app.schemas.strategy import StrategyResponse


class AgentCaseRequest(BaseModel):
    """Minimal context needed to run the full intelligence pipeline for one invoice."""

    invoice_id: str
    # Accept int or str — MOCK_INVOICES stores customer_id as int
    customer_id: Union[str, int]
    customer_name: str
    invoice_amount: float
    days_overdue: int
    payment_terms: int = 30
    customer_credit_score: int = 650
    customer_avg_days_to_pay: float = 30.0
    num_late_payments: int = 0
    customer_total_overdue: float = 0.0
    industry: str = "unknown"
    # Optional pre-fetched behavior data
    historical_on_time_ratio: float = 0.7
    avg_delay_days: float = 15.0
    repayment_consistency: float = 0.6
    partial_payment_frequency: float = 0.1
    payment_after_followup_count: int = 2
    total_invoices: int = 10
    deterioration_trend: float = 0.0
    invoice_acknowledgement_behavior: str = "normal"
    transaction_success_failure_pattern: float = 0.05

    @field_validator("customer_id", mode="before")
    @classmethod
    def coerce_customer_id_to_str(cls, v) -> str:
        """Ensure customer_id is always a string regardless of source type."""
        return str(v) if v is not None else "unknown"


class AgentCaseResponse(BaseModel):
    """Full intelligence output from the orchestrated agent pipeline."""

    invoice_id: str
    payment_behavior: PaymentBehaviorResponse
    delay_prediction: DelayPredictionResponse
    strategy: StrategyResponse
    business_summary: str
    recommended_action: str
    model_used: str = "gpt-4o"
