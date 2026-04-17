"""Pydantic schemas for cashflow and DSO forecasting."""

from pydantic import BaseModel
from typing import Optional


class DailyForecast(BaseModel):
    date: str  # ISO-8601
    predicted_inflow: float
    lower_bound: float
    upper_bound: float


class CashflowForecastResponse(BaseModel):
    # Core collections forecast
    next_7_days_inflow: float
    next_15_days_inflow: float
    next_30_days_inflow: float
    daily_breakdown: list[DailyForecast]
    confidence: float

    # Enhanced fields
    expected_7_day_collections: float
    expected_15_day_collections: float
    expected_30_day_collections: float
    amount_at_risk: float          # outstanding with >60% delay probability
    shortfall_signal: bool         # True if expected < 70% of outstanding
    borrower_concentration_risk: str  # "Low" | "Medium" | "High"
    overdue_carry_forward: float   # overdue amount not expected to clear in 30 days
