"""
AI Collector — ML Service Entry Point.

Exposes prediction and explainability endpoints consumed by the backend.
Models must be trained before inference will use them (falls back to heuristics).
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from inference.payment_predictor import predict as predict_payment
from inference.risk_classifier import classify as classify_risk
from explainability.shap_explainer import explain as shap_explain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Collector ML Service",
    version="1.0.0",
    description="XGBoost / LightGBM inference + SHAP explainability for the AI Collector platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class InvoiceFeatures(BaseModel):
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


class ExplainRequest(BaseModel):
    invoice_id: str
    features: dict


class BehaviorFeatures(BaseModel):
    """Input features for payment behavior classification."""

    customer_id: str
    customer_name: str
    historical_on_time_ratio: float
    avg_delay_days: float
    repayment_consistency: float
    partial_payment_frequency: float
    prior_delayed_invoice_count: int
    payment_after_followup_count: int
    total_invoices: int
    deterioration_trend: float = 0.0
    invoice_acknowledgement_behavior: str = "normal"
    transaction_success_failure_pattern: float = 0.0


class DelayFeatures(BaseModel):
    """Enriched delay prediction input."""

    invoice_id: str
    invoice_amount: float
    days_overdue: int
    payment_terms: int = 30
    customer_avg_invoice_amount: float = 0.0
    customer_credit_score: int = 650
    customer_avg_days_to_pay: float = 30.0
    num_late_payments: int = 0
    customer_total_overdue: float = 0.0
    behavior_type: str | None = None
    on_time_ratio: float | None = None
    avg_delay_days_historical: float | None = None
    behavior_risk_score: float | None = None
    deterioration_trend: float | None = None
    followup_dependency: bool | None = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok", "service": "ml-service"}


@app.post("/predict/payment", tags=["Predictions"])
def predict_payment_endpoint(request: InvoiceFeatures) -> dict:
    """Return payment probability for 7, 15, and 30-day horizons."""
    try:
        result = predict_payment(request.model_dump())
        return {"invoice_id": request.invoice_id, **result, "model_version": "xgboost-v1"}
    except Exception as exc:
        logger.error("Payment prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/predict/risk", tags=["Predictions"])
def predict_risk_endpoint(request: InvoiceFeatures) -> dict:
    """Return risk classification (High/Medium/Low) with confidence score."""
    try:
        result = classify_risk(request.model_dump())
        return {"invoice_id": request.invoice_id, **result}
    except Exception as exc:
        logger.error("Risk classification failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/explain", tags=["Explainability"])
def explain_endpoint(request: ExplainRequest) -> dict:
    """Return top SHAP feature attributions for the 30-day payment model."""
    try:
        result = shap_explain(request.features, top_n=5)
        return {"invoice_id": request.invoice_id, **result}
    except Exception as exc:
        logger.error("SHAP explanation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/analyze/payment-behavior", tags=["Behavior"])
def analyze_behavior_endpoint(request: BehaviorFeatures) -> dict:
    """
    Payment behavior classification — placeholder for XGBoost-based model.

    Currently returns a rule-based classification. Replace with trained model
    when behavior training pipeline is complete.
    """
    on_time_pct = request.historical_on_time_ratio * 100
    followup_ratio = request.payment_after_followup_count / max(request.total_invoices, 1)

    # Composite risk score
    raw = (
        (1 - request.historical_on_time_ratio) * 0.25
        + min(1.0, request.avg_delay_days / 60) * 0.25
        + followup_ratio * 0.15
        + request.partial_payment_frequency * 0.10
        + max(0.0, request.deterioration_trend) * 0.10
        + request.transaction_success_failure_pattern * 0.15
    )
    behavior_risk_score = round(min(100.0, raw * 100), 1)

    trend = (
        "Worsening" if request.deterioration_trend > 0.2
        else "Improving" if request.deterioration_trend < -0.1
        else "Stable"
    )

    if on_time_pct >= 85 and request.avg_delay_days < 5:
        behavior_type = "Consistent Payer"
        payment_style = "Prompt + Autonomous"
    elif on_time_pct >= 65 and request.avg_delay_days < 15:
        behavior_type = "Occasional Late Payer"
        payment_style = "Mostly On-Time"
    elif followup_ratio >= 0.5:
        behavior_type = "Reminder Driven Payer"
        payment_style = "Requires Follow-Up"
    elif request.partial_payment_frequency >= 0.4:
        behavior_type = "Partial Payment Payer"
        payment_style = "Partial + Reminder Driven"
    elif on_time_pct < 35 or request.avg_delay_days > 30:
        behavior_type = "Chronic Delayed Payer"
        payment_style = "Chronic Late + High DPD"
    elif behavior_risk_score >= 75:
        behavior_type = "High Risk Defaulter"
        payment_style = "Erratic + Non-Responsive"
    else:
        behavior_type = "Occasional Late Payer"
        payment_style = "Intermittent Delays"

    nach_recommended = behavior_type in (
        "Reminder Driven Payer", "Partial Payment Payer", "Chronic Delayed Payer"
    )

    return {
        "customer_id": request.customer_id,
        "customer_name": request.customer_name,
        "behavior_type": behavior_type,
        "on_time_ratio": round(on_time_pct, 1),
        "avg_delay_days": round(request.avg_delay_days, 1),
        "trend": trend,
        "payment_style": payment_style,
        "behavior_risk_score": behavior_risk_score,
        "followup_dependency": followup_ratio >= 0.4,
        "nach_recommended": nach_recommended,
        "behavior_summary": (
            f"{request.customer_name} is classified as a '{behavior_type}'. "
            f"On-time payment ratio is {on_time_pct:.0f}% with an average delay of "
            f"{request.avg_delay_days:.0f} days. Payment trend is {trend.lower()}. "
            f"Behavior risk score: {behavior_risk_score}/100."
        ),
        "model_version": "ml-behavior-placeholder-v1",
    }


@app.post("/predict/delay", tags=["Predictions"])
def predict_delay_endpoint(request: DelayFeatures) -> dict:
    """
    Enhanced delay prediction — placeholder for behavior-aware ML model.

    Implements the same rule engine as the backend fallback; replace
    with trained XGBoost model when behavior features are trained.
    """
    overdue_factor = min(1.0, request.days_overdue / 90)
    credit_factor = max(0.0, (700 - request.customer_credit_score) / 400)
    late_factor = min(1.0, request.num_late_payments / 10)

    behavior_factor = 0.0
    if request.on_time_ratio is not None:
        behavior_factor += (100 - request.on_time_ratio) / 100 * 0.25
    if request.behavior_risk_score is not None:
        behavior_factor += (request.behavior_risk_score / 100) * 0.15
    if request.followup_dependency:
        behavior_factor += 0.10

    delay_prob = min(0.98, max(0.02,
        overdue_factor * 0.30
        + credit_factor * 0.15
        + late_factor * 0.15
        + behavior_factor
    ))
    delay_prob = round(delay_prob, 4)
    risk_score = int(delay_prob * 100)
    risk_tier = "High" if risk_score >= 65 else "Medium" if risk_score >= 35 else "Low"

    top_drivers = []
    if request.days_overdue > 0:
        top_drivers.append(f"{request.days_overdue} days already overdue")
    if request.num_late_payments >= 3:
        top_drivers.append(f"{request.num_late_payments} prior delays")
    if request.customer_credit_score < 600:
        top_drivers.append(f"Credit score {request.customer_credit_score} below threshold")
    if request.behavior_type and "Chronic" in request.behavior_type:
        top_drivers.append("Chronic delayed payer pattern")
    if not top_drivers:
        top_drivers.append("Standard risk profile")

    return {
        "invoice_id": request.invoice_id,
        "delay_probability": delay_prob,
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "top_drivers": top_drivers[:4],
        "detailed_drivers": [
            {"driver": d, "impact": "high", "direction": "increases_risk"}
            for d in top_drivers[:4]
        ],
        "model_version": "ml-delay-placeholder-v1",
    }
