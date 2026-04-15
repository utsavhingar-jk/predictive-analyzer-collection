"""
Cashflow forecast service.

Generates a daily cashflow inflow forecast for the next 30 days using
invoice due dates + payment probability predictions.
"""

from datetime import date, timedelta
import random

from app.schemas.forecast import CashflowForecastResponse, DailyForecast
from app.utils.mock_data import MOCK_INVOICES


class CashflowService:
    def forecast(self) -> CashflowForecastResponse:
        """
        Build a 30-day cashflow forecast from open invoices.

        Each invoice contributes expected_inflow = amount × pay_probability
        distributed across the forecast window based on its due date.
        """
        today = date.today()
        daily: dict[date, dict] = {}

        for i in range(30):
            d = today + timedelta(days=i)
            daily[d] = {"predicted": 0.0, "lower": 0.0, "upper": 0.0}

        for inv in MOCK_INVOICES:
            due = inv["due_date"]
            amount = inv["amount"]
            pay_prob = inv.get("pay_30_days", 0.6)

            # Distribute expected inflow around the due date (±7 day window)
            for offset in range(-3, 4):
                target_date = due + timedelta(days=offset)
                if target_date not in daily:
                    continue
                weight = max(0.0, 1.0 - abs(offset) * 0.15)
                contribution = amount * pay_prob * weight / 4  # spread
                daily[target_date]["predicted"] += contribution
                daily[target_date]["lower"] += contribution * 0.75
                daily[target_date]["upper"] += contribution * 1.25

        breakdown: list[DailyForecast] = []
        total_7 = 0.0
        total_30 = 0.0

        for i, (day, vals) in enumerate(sorted(daily.items())):
            df = DailyForecast(
                date=day.isoformat(),
                predicted_inflow=round(vals["predicted"], 2),
                lower_bound=round(vals["lower"], 2),
                upper_bound=round(vals["upper"], 2),
            )
            breakdown.append(df)
            total_30 += vals["predicted"]
            if i < 7:
                total_7 += vals["predicted"]

        return CashflowForecastResponse(
            next_7_days_inflow=round(total_7, 2),
            next_30_days_inflow=round(total_30, 2),
            daily_breakdown=breakdown,
            confidence=0.82,
        )
