"""
Enhanced Delay Prediction API routes.

Endpoints:
  POST /predict/delay  — enriched delay prediction with behavior context + top drivers
"""

from fastapi import APIRouter

from app.schemas.delay import DelayPredictionRequest, DelayPredictionResponse
from app.services.delay_service import DelayService

router = APIRouter(prefix="/predict", tags=["Predictions"])

delay_svc = DelayService()


@router.post(
    "/delay",
    response_model=DelayPredictionResponse,
    summary="Enhanced delay prediction",
    description=(
        "Predicts delay probability using invoice context + payment behavior profile. "
        "Returns risk score (0–100), risk tier, and human-readable top drivers."
    ),
)
async def predict_delay(request: DelayPredictionRequest) -> DelayPredictionResponse:
    return await delay_svc.predict(request)
