"""Pydantic schemas for cashflow and DSO forecasting."""

from pydantic import BaseModel


class DailyForecast(BaseModel):
    date: str  # ISO-8601
    predicted_inflow: float
    lower_bound: float
    upper_bound: float


class CashflowForecastResponse(BaseModel):
    next_7_days_inflow: float
    next_30_days_inflow: float
    daily_breakdown: list[DailyForecast]
    confidence: float
