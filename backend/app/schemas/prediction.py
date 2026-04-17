"""Pydantic schemas for all ML prediction payloads."""

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.explainability import FeatureDriver, PredictionOutputDrivers


# ─── Payment Prediction ──────────────────────────────────────────────────────

class PaymentPredictionRequest(BaseModel):
    """Features required to predict payment probability for a single invoice."""

    invoice_id: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)
    customer_credit_score: int = Field(..., ge=300, le=900)
    customer_avg_days_to_pay: float = Field(..., ge=0)
    payment_terms: int = Field(default=30, ge=1)
    num_previous_invoices: int = Field(default=1, ge=1)
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
    llm_used: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None
    feature_drivers_by_horizon: list[PredictionOutputDrivers] = Field(default_factory=list)


# ─── Default Prediction ──────────────────────────────────────────────────────

class DefaultPredictionRequest(PaymentPredictionRequest):
    """Features required to predict the probability the invoice remains unpaid after 30 days."""


class DefaultPredictionResponse(BaseModel):
    """Probability that the invoice will still be unpaid after 30 days."""

    invoice_id: str
    default_probability: float = Field(..., ge=0, le=1)
    default_risk_tier: str  # "High" | "Medium" | "Low"
    confidence: float = Field(..., ge=0, le=1)
    model_version: str = "xgboost-default-v1"
    prediction_source: str = "ml"  # "ml" | "rule-based"
    llm_refined: bool = False
    llm_used: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None
    feature_drivers: list[FeatureDriver] = Field(default_factory=list)


# ─── Risk Classification ──────────────────────────────────────────────────────

class RiskClassificationRequest(BaseModel):
    invoice_id: str
    invoice_amount: float = Field(..., gt=0)
    days_overdue: int = Field(..., ge=0)
    customer_credit_score: int = Field(..., ge=300, le=900)
    customer_avg_days_to_pay: float = Field(..., ge=0)
    payment_terms: int = Field(default=30, ge=1)
    num_previous_invoices: int = Field(default=1, ge=1)
    num_late_payments: int = Field(default=0, ge=0)
    industry: str = "unknown"
    customer_total_overdue: float = 0.0


class RiskClassificationResponse(BaseModel):
    invoice_id: str
    risk_label: str  # "High" | "Medium" | "Low"
    risk_score: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    model_version: str = "lgbm-v1"
    prediction_source: str = "ml"  # "ml" | "ml+llm" | "rule-based"
    llm_refined: bool = False
    llm_used: bool = False
    used_fallback: bool = False
    explanation: Optional[str] = None
    feature_drivers: list[FeatureDriver] = Field(default_factory=list)


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
    default_probability: Optional[float] = None
    default_risk_tier: Optional[str] = None
    recommended_action: Optional[str] = None
    priority_rank: Optional[int] = None
    urgency: Optional[str] = None
    risk_tier: Optional[str] = None
    behavior_type: Optional[str] = None
    nach_recommended: Optional[bool] = None
    pay_7_days: Optional[float] = None
    pay_15_days: Optional[float] = None
    pay_30_days: Optional[float] = None
    delay_confidence: Optional[float] = None
    used_fallback: bool = False
