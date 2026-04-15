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
