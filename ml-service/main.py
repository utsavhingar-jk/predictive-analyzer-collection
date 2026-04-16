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
from inference.delay_predictor import predict_delay
from inference.behavior_predictor import predict_behavior
from inference.borrower_predictor import predict_borrower_risk
from explainability.shap_explainer import explain as shap_explain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Collector ML Service",
    version="1.0.0",
    description="XGBoost inference + SHAP explainability for the AI Collector platform.",
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
    num_previous_invoices: int = 10
    industry: str = "unknown"
    customer_total_overdue: float = 0.0
    behavior_type: str | None = None
    on_time_ratio: float | None = None
    avg_delay_days_historical: float | None = None
    behavior_risk_score: float | None = None
    deterioration_trend: float | None = None
    followup_dependency: bool | None = None


class BorrowerInvoiceFeatures(BaseModel):
    invoice_id: str
    amount: float
    days_overdue: int
    status: str
    risk_label: str
    delay_probability: float
    pay_30_days: float
    recommended_action: str | None = None


class BorrowerFeatures(BaseModel):
    customer_id: str
    customer_name: str
    industry: str = "unknown"
    credit_score: int = 650
    avg_days_to_pay: float = 30.0
    payment_terms: int = 30
    num_late_payments: int = 0
    portfolio_total_outstanding: float = 0.0
    invoices: list[BorrowerInvoiceFeatures] = []


class BorrowerPortfolioBatchRequest(BaseModel):
    """
    Full portfolio in one request — ML-only analysis (no backend / OpenAI).
    Set portfolio_total_outstanding once; it is applied to borrowers missing it.
    """

    portfolio_total_outstanding: float = 0.0
    borrowers: list[BorrowerFeatures]


def borrower_prediction_dict(request: BorrowerFeatures) -> dict:
    """
    Borrower-level metrics — XGBoost risk score when trained, else rule-based score.
    Shared by POST /predict/borrower and POST /predict/borrowers/portfolio.
    """
    invoices = request.invoices or []
    if not invoices:
        return {
            "customer_id": request.customer_id,
            "customer_name": request.customer_name,
            "industry": request.industry,
            "total_outstanding": 0.0,
            "total_overdue": 0.0,
            "open_invoice_count": 0,
            "overdue_invoice_count": 0,
            "concentration_pct": 0.0,
            "weighted_delay_probability": 0.0,
            "borrower_risk_score": 0,
            "borrower_risk_tier": "Low",
            "expected_recovery_amount": 0.0,
            "expected_recovery_rate": 0.0,
            "at_risk_amount": 0.0,
            "recovery_confidence": "High",
            "borrower_dso": request.avg_days_to_pay,
            "dso_vs_portfolio": "On Par",
            "escalation_recommended": False,
            "nach_recommended": False,
            "relationship_action": "No Open Invoices",
            "invoices": [],
        "borrower_summary": f"{request.customer_name} has no open invoices.",
        "model_version": "ml-borrower-rules-v1",
        "feature_drivers": [],
        "explanation": "No open invoices were available, so borrower-level ML feature drivers could not be computed.",
    }

    total_outstanding = sum(float(inv.amount or 0.0) for inv in invoices)
    total_overdue = sum(float(inv.amount or 0.0) for inv in invoices if inv.status == "overdue")
    open_count = len(invoices)
    overdue_count = sum(1 for inv in invoices if inv.status == "overdue")
    weighted_delay_probability = (
        sum(float(inv.delay_probability or 0.0) * float(inv.amount or 0.0) for inv in invoices) / max(total_outstanding, 1.0)
    )
    weighted_delay_probability = round(min(1.0, max(0.0, weighted_delay_probability)), 4)
    expected_recovery_amount = sum(float(inv.amount or 0.0) * float(inv.pay_30_days or 0.0) for inv in invoices)
    expected_recovery_rate = round(expected_recovery_amount / max(total_outstanding, 1.0), 4)
    at_risk_amount = round(sum(float(inv.amount or 0.0) for inv in invoices if float(inv.delay_probability or 0.0) > 0.60), 2)

    concentration_raw = total_outstanding / max(request.portfolio_total_outstanding, 1.0)

    ml_br = predict_borrower_risk(request.model_dump())
    if ml_br:
        borrower_risk_score = int(round(ml_br["borrower_risk_score"]))
        borrower_risk_tier = ml_br["borrower_risk_tier"]
        br_version = "xgboost-borrower-v1"
        borrower_feature_drivers = ml_br.get("feature_drivers", [])
        borrower_explanation = ml_br.get("explanation")
    else:
        overdue_ratio = total_overdue / max(total_outstanding, 1.0)
        credit_factor = max(0.0, (700 - request.credit_score) / 400)
        late_factor = min(1.0, request.num_late_payments / 10)
        concentration_factor = min(1.0, concentration_raw / 0.5)
        score_raw = (
            weighted_delay_probability * 0.40
            + overdue_ratio * 0.20
            + credit_factor * 0.20
            + late_factor * 0.10
            + concentration_factor * 0.10
        )
        borrower_risk_score = int(min(100, round(score_raw * 100)))
        borrower_risk_tier = "High" if borrower_risk_score >= 65 else "Medium" if borrower_risk_score >= 35 else "Low"
        br_version = "ml-borrower-rules-v1"
        borrower_feature_drivers = []
        borrower_explanation = "Borrower rule fallback used weighted delay, overdue ratio, credit stress, late payments, and concentration."

    concentration_pct = round(concentration_raw * 100, 1)

    borrower_dso = request.avg_days_to_pay
    if borrower_dso < 45 * 0.85:
        dso_vs_portfolio = "Better"
    elif borrower_dso > 45 * 1.15:
        dso_vs_portfolio = "Worse"
    else:
        dso_vs_portfolio = "On Par"

    nach_recommended = borrower_risk_tier == "High" and request.num_late_payments >= 3
    escalation_recommended = (
        (borrower_risk_tier == "High" and total_outstanding > 50_000)
        or weighted_delay_probability > 0.75
        or (overdue_count >= 2 and total_overdue > 30_000)
    )
    recovery_confidence = "High" if expected_recovery_rate >= 0.70 else "Medium" if expected_recovery_rate >= 0.40 else "Low"

    if borrower_risk_tier == "High" and total_outstanding > 100_000:
        relationship_action = "Escalate Relationship — Legal Review"
    elif borrower_risk_tier == "High" and weighted_delay_probability > 0.75:
        relationship_action = "Suspend Credit Facility + Demand Letter"
    elif borrower_risk_tier == "High" and nach_recommended:
        relationship_action = "Activate NACH Mandate + Collection Call"
    elif borrower_risk_tier == "High":
        relationship_action = "Place on Credit Hold + Escalate"
    elif borrower_risk_tier == "Medium" and overdue_count >= 2:
        relationship_action = "Collection Call + Payment Plan"
    elif borrower_risk_tier == "Medium":
        relationship_action = "Follow-up Email + Call"
    else:
        relationship_action = "Standard Reminder Cycle"

    borrower_summary = (
        f"{request.customer_name} carries total AR exposure of ${total_outstanding:,.0f} "
        f"across {open_count} open invoices ({overdue_count} overdue). "
        f"Borrower risk score is {borrower_risk_score}/100 ({borrower_risk_tier}) "
        f"with weighted delay probability {weighted_delay_probability:.0%}."
    )

    return {
        "customer_id": request.customer_id,
        "customer_name": request.customer_name,
        "industry": request.industry,
        "total_outstanding": round(total_outstanding, 2),
        "total_overdue": round(total_overdue, 2),
        "open_invoice_count": open_count,
        "overdue_invoice_count": overdue_count,
        "concentration_pct": concentration_pct,
        "weighted_delay_probability": weighted_delay_probability,
        "borrower_risk_score": borrower_risk_score,
        "borrower_risk_tier": borrower_risk_tier,
        "expected_recovery_amount": round(expected_recovery_amount, 2),
        "expected_recovery_rate": expected_recovery_rate,
        "at_risk_amount": at_risk_amount,
        "recovery_confidence": recovery_confidence,
        "borrower_dso": borrower_dso,
        "dso_vs_portfolio": dso_vs_portfolio,
        "escalation_recommended": escalation_recommended,
        "nach_recommended": nach_recommended,
        "relationship_action": relationship_action,
        "invoices": [inv.model_dump() for inv in invoices],
        "borrower_summary": borrower_summary,
        "model_version": br_version,
        "feature_drivers": borrower_feature_drivers,
        "explanation": borrower_explanation,
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok", "service": "ml-service"}


@app.post("/predict/payment", tags=["Predictions"])
def predict_payment_endpoint(request: InvoiceFeatures) -> dict:
    """Return payment probability for 7, 15, and 30-day horizons (ML per horizon, then heuristic fallback)."""
    try:
        result = predict_payment(request.model_dump())
        return {"invoice_id": request.invoice_id, **result}
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
@app.post("/predict/explain", tags=["Explainability"])
def explain_endpoint(request: ExplainRequest) -> dict:
    """Return top SHAP feature attributions for the 30-day payment model (ML first; heuristic if unavailable)."""
    try:
        result = shap_explain(request.features, top_n=5)
        return {"invoice_id": request.invoice_id, **result}
    except Exception as exc:
        logger.error("SHAP explanation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/analyze/payment-behavior", tags=["Behavior"])
def analyze_behavior_endpoint(request: BehaviorFeatures) -> dict:
    """
    Payment behavior classification — tries XGBoost multiclass first, then rule-based labels.
    """
    ml = predict_behavior(request.model_dump())
    on_time_pct = request.historical_on_time_ratio * 100
    followup_ratio = request.payment_after_followup_count / max(request.total_invoices, 1)

    # Composite risk score (used for summary + styling when model missing)
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

    if ml:
        behavior_type = ml["behavior_type"]
        payment_style = {
            "Consistent Payer": "Prompt + Autonomous",
            "Occasional Late Payer": "Mostly On-Time",
            "Reminder Driven Payer": "Requires Follow-Up",
            "Partial Payment Payer": "Partial + Reminder Driven",
            "Chronic Delayed Payer": "Chronic Late + High DPD",
            "High Risk Defaulter": "Erratic + Non-Responsive",
        }.get(behavior_type, "Intermittent Delays")
        version = "xgboost-behavior-v1"
        feature_drivers = ml.get("feature_drivers", [])
        explanation = ml.get("explanation")
    else:
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
        version = "ml-behavior-rules-v1"
        feature_drivers = []
        explanation = "Behavior rule fallback used on-time ratio, delay days, follow-up dependence, and payment pattern signals."

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
        "model_version": version,
        "feature_drivers": feature_drivers,
        "explanation": explanation,
    }


@app.post("/predict/delay", tags=["Predictions"])
def predict_delay_endpoint(request: DelayFeatures) -> dict:
    """
    Delay probability — XGBoost regressor first when trained; rule-based estimate if missing or on inference error.
    """
    ml = predict_delay(request.model_dump())
    if ml:
        delay_prob = round(ml["delay_probability"], 4)
        version = "xgboost-delay-v1"
        feature_drivers = ml.get("feature_drivers", [])
        explanation = ml.get("explanation")
    else:
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
        version = "ml-delay-rules-v1"
        feature_drivers = []
        explanation = "Delay rule fallback used overdue days, credit stress, historical late payments, and behavior context."

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
        "model_version": version,
        "feature_drivers": feature_drivers,
        "explanation": explanation,
    }


@app.post("/predict/borrower", tags=["Predictions"])
def predict_borrower_endpoint(request: BorrowerFeatures) -> dict:
    """Single-borrower prediction (same logic as batch portfolio)."""
    return borrower_prediction_dict(request)


@app.post("/predict/borrowers/portfolio", tags=["Predictions"])
def predict_borrowers_portfolio_ml(body: BorrowerPortfolioBatchRequest) -> list[dict]:
    """
    Analyze the full borrower portfolio with ML only — no backend or OpenAI.

    Body: portfolio_total_outstanding plus one BorrowerFeatures object per borrower
    (each must include invoices). Missing per-borrower portfolio_total_outstanding
    is filled from the top-level field.
    """
    pt = max(0.0, body.portfolio_total_outstanding)
    out: list[dict] = []
    for b in body.borrowers:
        d = b.model_dump()
        if float(d.get("portfolio_total_outstanding") or 0) <= 0:
            d["portfolio_total_outstanding"] = pt
        out.append(borrower_prediction_dict(BorrowerFeatures(**d)))
    return out
