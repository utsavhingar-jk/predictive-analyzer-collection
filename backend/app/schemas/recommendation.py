"""Pydantic schemas for the OpenAI prescriptive analytics engine."""

from typing import Optional
from pydantic import BaseModel


class CustomerHistory(BaseModel):
    """Summarized customer payment behaviour passed to the AI agent."""

    customer_name: str
    avg_days_to_pay: float
    num_late_payments: int
    num_disputes: int = 0
    total_outstanding: float
    credit_score: int
    industry: str = "unknown"


class RecommendationRequest(BaseModel):
    """Full context bundle sent to the GPT-4o recommendation agent."""

    invoice_id: str
    invoice_amount: float
    days_overdue: int
    risk_label: str
    pay_7_days: float
    pay_15_days: float
    pay_30_days: float
    customer_history: CustomerHistory


class RecommendationResponse(BaseModel):
    """Structured output from the GPT-4o collection agent."""

    invoice_id: str
    recommended_action: str  # e.g. "Call Customer", "Send Final Notice", "Escalate"
    priority: str  # "Critical" | "High" | "Medium" | "Low"
    timeline: str  # e.g. "Within 24 Hours"
    reasoning: str
    additional_notes: Optional[str] = None
    model_used: str = "gpt-4o"
