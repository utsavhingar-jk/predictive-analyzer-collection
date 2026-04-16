"""Pydantic schemas for all ML prediction payloads."""

from typing import Optional
from pydantic import BaseModel, Field


# ─── Payment Prediction ──────────────────────────────────────────────────────

class PaymentPredictionRequest(BaseModel):
    """Features required to predict payment probability for a single invoice."""

    invoice_id: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)
    customer_credit_score: int = Field(..., ge=300, le=850)
    customer_avg_days_to_pay: float = Field(..., ge=0)
    payment_terms: int = Field(default=30, ge=0)
    num_previous_invoices: int = Field(default=0, ge=0)
    num_late_payments: int = Field(default=0, ge=0)
    industry: str = "unknown"
    customer_total_overdue: float = 0.0


class PaymentPredictionResponse(BaseModel):
    """Probability of payment within 7, 15, and 30 days."""

    invoice_id: str
    pay_7_days: float = Field(..., ge=0, le=1)
    pay_15_days: float = Field(..., ge=0, le=1)
    pay_30_days: float = Field(..., ge=0, le=1)
    model_version: str = "xgboost-v1"
    prediction_source: str = "ml"  # "ml" | "ml+llm" | "rule-based"
    llm_refined: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None


# ─── Risk Classification ──────────────────────────────────────────────────────

class RiskClassificationRequest(BaseModel):
    invoice_id: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)
    customer_credit_score: int = Field(..., ge=300, le=850)
    customer_avg_days_to_pay: float = Field(..., ge=0)
    payment_terms: int = Field(default=30, ge=0)
    num_late_payments: int = Field(default=0, ge=0)
    customer_total_overdue: float = 0.0


class RiskClassificationResponse(BaseModel):
    invoice_id: str
    risk_label: str  # "High" | "Medium" | "Low"
    risk_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    model_version: str = "lgbm-v1"
    prediction_source: str = "ml"  # "ml" | "ml+llm" | "rule-based"
    llm_refined: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None


# ─── DSO Prediction ──────────────────────────────────────────────────────────

class DSOPredictionResponse(BaseModel):
    predicted_dso: float  # days
    current_dso: float
    dso_trend: str  # "improving" | "stable" | "worsening"
    benchmark_dso: float = 45.0


# ─── SHAP Explanation ────────────────────────────────────────────────────────

class ShapFeature(BaseModel):
    feature_name: str
    feature_value: float
    shap_value: float
    impact: str  # "positive" | "negative"


class ShapExplanationResponse(BaseModel):
    invoice_id: str
    top_features: list[ShapFeature]
    base_value: float
    prediction_value: float


# ─── Prioritized Invoice ─────────────────────────────────────────────────────

class PrioritizedInvoice(BaseModel):
    invoice_id: str
    customer_name: str
    amount: float
    days_overdue: int
    risk_label: str
    delay_probability: float
    priority_score: float  # amount × delay_probability
    recommended_action: Optional[str] = None
