"""Pydantic schemas for the agentic OpenAI function-calling endpoint."""

from typing import Any, Optional, Union
from pydantic import BaseModel, field_validator

from app.schemas.behavior import PaymentBehaviorResponse
from app.schemas.delay import DelayPredictionResponse
from app.schemas.strategy import StrategyResponse


# ── Reasoning trace models ────────────────────────────────────────────────────

class AgentToolCall(BaseModel):
    """
    Records one tool invocation the agent made during its reasoning loop.
    The frontend renders these as a step-by-step thinking trace.
    """
    step: int
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: dict[str, Any]
    agent_thought: Optional[str] = None   # GPT's reasoning before calling the tool


class AgentAskRequest(BaseModel):
    """
    Free-form question the agent will answer by calling tools autonomously.
    E.g. 'Which invoices need escalation today?' or 'Analyze INV-2024-004'
    """
    question: str
    invoice_id: Optional[str] = None
    customer_id: Optional[str] = None


class AgentAskResponse(BaseModel):
    """Response from free-form agentic question."""
    answer: str
    reasoning_trace: list[AgentToolCall]
    tools_called: list[str]
    iterations: int
    model_used: str = "gpt-4o"


# ── Structured case request (existing, kept for backward compat) ──────────────

class AgentCaseRequest(BaseModel):
    """Minimal context needed to run the full intelligence pipeline for one invoice."""

    invoice_id: str
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
        return str(v) if v is not None else "unknown"


class AgentCaseResponse(BaseModel):
    """
    Full intelligence output from the agentic pipeline.
    Now includes reasoning_trace so the UI can show every tool call GPT-4o made.
    """
    invoice_id: str
    payment_behavior: PaymentBehaviorResponse
    delay_prediction: DelayPredictionResponse
    strategy: StrategyResponse
    business_summary: str
    recommended_action: str
    model_used: str = "gpt-4o"
    # Agentic additions
    reasoning_trace: list[AgentToolCall] = []
    agent_iterations: int = 0
    tools_called: list[str] = []
