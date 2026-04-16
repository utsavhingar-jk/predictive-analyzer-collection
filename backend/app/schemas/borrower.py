"""Pydantic schemas for borrower-level prediction and risk aggregation."""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.explainability import FeatureDriver


class BorrowerInvoiceSummary(BaseModel):
    """Lightweight view of one invoice within a borrower's portfolio."""

    invoice_id: str
    amount: float
    days_overdue: int
    status: str
    risk_label: str
    delay_probability: float
    pay_30_days: float
    recommended_action: Optional[str] = None


class BorrowerPredictionRequest(BaseModel):
    """
    Request to compute borrower-level prediction.
    Caller can either pass raw invoice data OR just the customer_id
    to trigger a lookup from the portfolio.
    """

    customer_id: str
    customer_name: str
    industry: str = "unknown"
    credit_score: int = Field(default=650, ge=300, le=850)
    avg_days_to_pay: float = 30.0
    payment_terms: int = 30
    num_late_payments: int = 0
    total_outstanding: float = 0.0
    # List of open invoices for this borrower
    invoices: list[BorrowerInvoiceSummary] = []


class BorrowerRiskTrendPoint(BaseModel):
    """One data point for a borrower's rolling risk history (for charts)."""

    period: str          # e.g. "Jan 24", "Feb 24"
    risk_score: float
    delay_probability: float
    outstanding: float


class BorrowerPredictionResponse(BaseModel):
    """Full borrower-level risk intelligence output."""

    customer_id: str
    customer_name: str
    industry: str

    # ── Portfolio exposure ────────────────────────────────────────────────────
    total_outstanding: float
    total_overdue: float
    open_invoice_count: int
    overdue_invoice_count: int
    concentration_pct: float           # this borrower as % of total portfolio AR

    # ── Aggregate risk ────────────────────────────────────────────────────────
    weighted_delay_probability: float  # amount-weighted avg delay prob across invoices
    borrower_risk_score: int           # 0–100
    borrower_risk_tier: str            # High | Medium | Low

    # ── Recovery forecast ─────────────────────────────────────────────────────
    expected_recovery_amount: float    # amount × pay_probability summed
    expected_recovery_rate: float      # expected_recovery / total_outstanding (0–1)
    at_risk_amount: float              # outstanding with delay_prob > 0.60
    recovery_confidence: str           # "High" | "Medium" | "Low"

    # ── Borrower-specific DSO ──────────────────────────────────────────────────
    borrower_dso: float                # this customer's avg days to pay
    dso_vs_portfolio: str              # "Better" | "On Par" | "Worse" than portfolio avg (45d)

    # ── Escalation signals ─────────────────────────────────────────────────────
    escalation_recommended: bool
    nach_recommended: bool
    relationship_action: str           # overall borrower-level recommended action

    # ── Invoice breakdown ──────────────────────────────────────────────────────
    invoices: list[BorrowerInvoiceSummary]

    # ── Summary ───────────────────────────────────────────────────────────────
    borrower_summary: str
    model_version: str = "borrower-rule-v1"
    prediction_source: str = "rule-based"  # "ml" | "ml+llm" | "rule-based"
    llm_refined: bool = False
    used_fallback: bool = True
    explanation: Optional[str] = None
    feature_drivers: list[FeatureDriver] = Field(default_factory=list)


class BorrowerPortfolioItem(BaseModel):
    """Compact borrower row for the portfolio ranking table."""

    customer_id: str
    customer_name: str
    industry: str
    total_outstanding: float
    overdue_invoice_count: int
    borrower_risk_tier: str
    borrower_risk_score: int
    weighted_delay_probability: float
    expected_recovery_rate: float
    at_risk_amount: float
    escalation_recommended: bool
    relationship_action: str
    concentration_pct: float
