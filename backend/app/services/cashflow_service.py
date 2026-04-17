"""Predictive cashflow forecast built from portfolio payment and delay models."""

from datetime import date, timedelta

from app.schemas.forecast import CashflowForecastResponse, DailyForecast
from app.services.portfolio_intelligence_service import PortfolioIntelligenceService


class CashflowService:
    SHORTFALL_THRESHOLD = 0.70

    def __init__(self) -> None:
        self.portfolio_svc = PortfolioIntelligenceService()

    async def forecast(self) -> CashflowForecastResponse:
        results = await self.portfolio_svc.build_portfolio_results()
        return self._build_forecast(results)

    def _build_forecast(self, results) -> CashflowForecastResponse:
        today = date.today()
        daily: dict[date, dict[str, float]] = {
            today + timedelta(days=offset): {"predicted": 0.0, "lower": 0.0, "upper": 0.0}
            for offset in range(30)
        }

        total_outstanding = 0.0
        amount_at_risk = 0.0
        overdue_carry_forward = 0.0
        weighted_confidence = 0.0
        customer_amounts: dict[str, float] = {}

        for result in results:
            amount = float(result.invoice["amount"])
            customer = str(result.invoice["customer_name"])
            total_outstanding += amount
            customer_amounts[customer] = customer_amounts.get(customer, 0.0) + amount
            weighted_confidence += amount * float(result.delay.confidence)

            if result.delay.delay_probability > 0.60:
                amount_at_risk += amount

            overdue_carry_forward += amount * max(1.0 - result.payment.pay_30_days, 0.0)

            bucket_0_7, bucket_8_15, bucket_16_30, _tail = (
                result.incremental_payment_probabilities()
            )
            for start_day, end_day, probability in (
                (0, 7, bucket_0_7),
                (7, 15, bucket_8_15),
                (15, 30, bucket_16_30),
            ):
                if probability <= 0:
                    continue
                daily_amount = amount * probability / max(end_day - start_day, 1)
                uncertainty = max(0.15, 1.0 - float(result.delay.confidence))
                lower_multiplier = max(0.55, 1.0 - uncertainty * 0.8)
                upper_multiplier = 1.0 + uncertainty * 0.8

                for offset in range(start_day, end_day):
                    target = today + timedelta(days=offset)
                    if target not in daily:
                        continue
                    daily[target]["predicted"] += daily_amount
                    daily[target]["lower"] += daily_amount * lower_multiplier
                    daily[target]["upper"] += daily_amount * upper_multiplier

        breakdown: list[DailyForecast] = []
        total_7 = 0.0
        total_15 = 0.0
        total_30 = 0.0

        for index, forecast_day in enumerate(sorted(daily)):
            values = daily[forecast_day]
            breakdown.append(
                DailyForecast(
                    date=forecast_day.isoformat(),
                    predicted_inflow=round(values["predicted"], 2),
                    lower_bound=round(values["lower"], 2),
                    upper_bound=round(values["upper"], 2),
                )
            )
            total_30 += values["predicted"]
            if index < 15:
                total_15 += values["predicted"]
            if index < 7:
                total_7 += values["predicted"]

        if customer_amounts and total_outstanding > 0:
            max_single_exposure = max(customer_amounts.values())
            concentration_pct = max_single_exposure / total_outstanding
            if concentration_pct > 0.40:
                borrower_concentration = "High"
            elif concentration_pct > 0.20:
                borrower_concentration = "Medium"
            else:
                borrower_concentration = "Low"
        else:
            borrower_concentration = "Low"

        confidence = round(weighted_confidence / max(total_outstanding, 1.0), 4) if total_outstanding else 0.0
        shortfall = total_outstanding > 0 and (total_30 / total_outstanding) < self.SHORTFALL_THRESHOLD

        return CashflowForecastResponse(
            next_7_days_inflow=round(total_7, 2),
            next_15_days_inflow=round(total_15, 2),
            next_30_days_inflow=round(total_30, 2),
            daily_breakdown=breakdown,
            confidence=confidence,
            expected_7_day_collections=round(total_7, 2),
            expected_15_day_collections=round(total_15, 2),
            expected_30_day_collections=round(total_30, 2),
            amount_at_risk=round(amount_at_risk, 2),
            shortfall_signal=shortfall,
            borrower_concentration_risk=borrower_concentration,
            overdue_carry_forward=round(overdue_carry_forward, 2),
        )
