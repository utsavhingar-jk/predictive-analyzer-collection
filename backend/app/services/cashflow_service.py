"""
Enhanced Cashflow Forecast Service.

Incorporates:
- predicted pay probabilities
- delay probabilities (1 - pay_30_days)
- invoice amount concentration
- borrower concentration risk
- overdue carry-forward estimate
- shortfall signal
"""

from datetime import date, timedelta

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.forecast import CashflowForecastResponse, DailyForecast
from app.services.risk_scoring import (
    build_amount_reference,
    delay_probability_from_score,
    risk_score,
)


class CashflowService:
    # Shortfall threshold: flag if expected collections < this % of total outstanding
    SHORTFALL_THRESHOLD = 0.70

    def forecast(self) -> CashflowForecastResponse:
        """
        Build an enhanced 30-day cashflow forecast.

        Each invoice contributes:
          expected_inflow = amount × pay_probability × recency_weight

        Additional signals:
          - amount_at_risk: sum of amounts with delay_prob > 0.60
          - overdue_carry_forward: expected uncollected overdue in 30d
          - borrower_concentration_risk: top single borrower as % of outstanding
          - shortfall_signal: expected_30d < 70% of total outstanding
        """
        with SessionLocal() as db:
            rows = db.execute(
                text(
                    """
                    SELECT
                        i.invoice_number AS invoice_id,
                        c.name AS customer_name,
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.due_date,
                        i.days_overdue,
                        i.status
                    FROM invoices i
                    LEFT JOIN customers c ON c.id = i.customer_id
                    WHERE i.status IN ('open', 'overdue')
                    """
                )
            ).mappings().all()

        invoices = []
        for row in rows:
            days_overdue = int(row["days_overdue"] or 0)
            pay_30 = max(0.05, min(0.95, 1.0 - (days_overdue / 45.0)))
            invoices.append(
                {
                    "invoice_id": row["invoice_id"],
                    "customer_name": row["customer_name"] or "Unknown Customer",
                    "amount": float(row["amount"] or 0),
                    "due_date": row["due_date"],
                    "status": row["status"],
                    "days_overdue": days_overdue,
                    "pay_30_days": pay_30,
                }
            )
        return self._build_forecast_from_invoices(invoices)

    def _build_forecast_from_invoices(self, invoices: list[dict]) -> CashflowForecastResponse:
        today = date.today()
        daily: dict[date, dict] = {}

        for i in range(30):
            d = today + timedelta(days=i)
            daily[d] = {"predicted": 0.0, "lower": 0.0, "upper": 0.0}

        total_outstanding = 0.0
        amount_at_risk = 0.0
        overdue_carry_forward = 0.0
        customer_amounts: dict[str, float] = {}
        amount_reference = build_amount_reference(inv["amount"] for inv in invoices)

        for inv in invoices:
            if inv["status"] not in ("open", "overdue"):
                continue

            due = inv["due_date"]
            amount = inv["amount"]
            combined_risk = risk_score(int(inv.get("days_overdue", 0) or 0), amount, amount_reference)
            delay_prob = delay_probability_from_score(combined_risk)
            pay_prob = max(0.05, min(0.95, 1.0 - delay_prob))
            customer = inv["customer_name"]

            total_outstanding += amount
            customer_amounts[customer] = customer_amounts.get(customer, 0.0) + amount

            # Track amount at risk (delay_prob > 0.60)
            if delay_prob > 0.60:
                amount_at_risk += amount

            # Overdue carry-forward: expected uncollected in 30 days
            overdue_carry_forward += amount * delay_prob

            # For overdue invoices, spread expected recovery over near-term horizon.
            if due < today:
                due = today + timedelta(days=min(max(inv.get("days_overdue", 0) // 3, 1), 10))

            # Distribute expected inflow across forecast window
            for offset in range(-3, 4):
                target_date = due + timedelta(days=offset)
                if target_date not in daily:
                    continue
                weight = max(0.0, 1.0 - abs(offset) * 0.15)
                contribution = amount * pay_prob * weight / 4
                daily[target_date]["predicted"] += contribution
                daily[target_date]["lower"] += contribution * 0.75
                daily[target_date]["upper"] += contribution * 1.25

        # Build breakdown
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

        # Borrower concentration risk
        if customer_amounts and total_outstanding > 0:
            max_single = max(customer_amounts.values())
            concentration_pct = max_single / total_outstanding
            if concentration_pct > 0.40:
                borrower_concentration = "High"
            elif concentration_pct > 0.20:
                borrower_concentration = "Medium"
            else:
                borrower_concentration = "Low"
        else:
            borrower_concentration = "Low"

        # Shortfall signal
        shortfall = total_outstanding > 0 and (total_30 / total_outstanding) < self.SHORTFALL_THRESHOLD

        return CashflowForecastResponse(
            next_7_days_inflow=round(total_7, 2),
            next_30_days_inflow=round(total_30, 2),
            daily_breakdown=breakdown,
            confidence=0.82,
            # Enhanced fields
            expected_7_day_collections=round(total_7, 2),
            expected_30_day_collections=round(total_30, 2),
            amount_at_risk=round(amount_at_risk, 2),
            shortfall_signal=shortfall,
            borrower_concentration_risk=borrower_concentration,
            overdue_carry_forward=round(overdue_carry_forward, 2),
        )
