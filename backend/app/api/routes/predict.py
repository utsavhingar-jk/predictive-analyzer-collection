"""
Prediction API routes.

Endpoints:
  POST /predict/payment  — payment probability (7/15/30 days)
  POST /predict/default  — default probability (still unpaid after 30 days)
  POST /predict/risk     — risk classification (High/Medium/Low)
  GET  /predict/dso      — DSO prediction
  POST /predict/explain  — SHAP explainability for a single invoice
"""

from fastapi import APIRouter, HTTPException

from app.schemas.prediction import (
    DefaultPredictionRequest,
    DefaultPredictionResponse,
    DSOPredictionResponse,
    PaymentPredictionRequest,
    PaymentPredictionResponse,
    RiskClassificationRequest,
    RiskClassificationResponse,
    ShapExplanationResponse,
)
from app.services.dso_service import DSOService
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predict", tags=["Predictions"])

prediction_svc = PredictionService()
dso_svc = DSOService()


@router.post(
    "/payment",
    response_model=PaymentPredictionResponse,
    summary="Predict payment probability",
    description=(
        "Returns the probability that the invoice will be paid "
        "within 7, 15, and 30 days using the XGBoost model."
    ),
)
async def predict_payment(
    request: PaymentPredictionRequest,
) -> PaymentPredictionResponse:
    return await prediction_svc.predict_payment(request)


@router.post(
    "/default",
    response_model=DefaultPredictionResponse,
    summary="Predict default probability",
    description=(
        "Returns the probability that the invoice will still be unpaid after 30 days "
        "using the dedicated XGBoost default-proxy model."
    ),
)
async def predict_default(
    request: DefaultPredictionRequest,
) -> DefaultPredictionResponse:
    return await prediction_svc.predict_default(request)


@router.post(
    "/risk",
    response_model=RiskClassificationResponse,
    summary="Classify invoice risk",
    description="Classifies an invoice as High, Medium, or Low risk using LightGBM.",
)
async def classify_risk(
    request: RiskClassificationRequest,
) -> RiskClassificationResponse:
    return await prediction_svc.classify_risk(request)


@router.get(
    "/dso",
    response_model=DSOPredictionResponse,
    summary="Predict DSO",
    description="Returns current and predicted Days Sales Outstanding for the portfolio.",
)
async def predict_dso() -> DSOPredictionResponse:
    return await dso_svc.predict_dso()


@router.post(
    "/explain",
    response_model=ShapExplanationResponse,
    summary="SHAP explanation for a prediction",
    description="Returns top SHAP features explaining the risk/payment prediction for an invoice.",
)
async def explain_prediction(
    invoice_id: str,
    features: dict,
) -> ShapExplanationResponse:
    return await prediction_svc.explain(invoice_id, features)
