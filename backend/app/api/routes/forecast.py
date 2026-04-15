"""
Forecast API routes.

Endpoints:
  GET /forecast/cashflow — 7-day and 30-day cash inflow forecast with daily breakdown
"""

from fastapi import APIRouter

from app.schemas.forecast import CashflowForecastResponse
from app.services.cashflow_service import CashflowService

router = APIRouter(prefix="/forecast", tags=["Forecasting"])

cashflow_svc = CashflowService()


@router.get(
    "/cashflow",
    response_model=CashflowForecastResponse,
    summary="Cash flow forecast",
    description=(
        "Forecasts expected cash inflows for the next 7 and 30 days "
        "using payment probabilities weighted by invoice amounts."
    ),
)
def get_cashflow_forecast() -> CashflowForecastResponse:
    return cashflow_svc.forecast()
