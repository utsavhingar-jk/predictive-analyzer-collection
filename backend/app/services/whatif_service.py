"""
What-If scenario simulation service.

Allows collectors and managers to model the impact of strategy changes
(efficiency improvements, discounts, follow-up timing shifts) on key AR metrics.
"""

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.whatif import WhatIfRequest, WhatIfResponse


class WhatIfService:
    DEFAULT_RECOVERY_PCT: float = 68.0
    DEFAULT_DSO: float = 45.0
    DEFAULT_CASHFLOW: float = 0.0

    def _baseline_metrics(self) -> tuple[float, float, float]:
        """
        Build baseline scenario metrics from live invoice data.

        - baseline_recovery_pct: weighted 30-day pay probability
        - baseline_cashflow: expected 30-day collections (weighted)
        - baseline_dso: weighted expected collection delay in days
        """
        with SessionLocal() as db:
            rows = db.execute(
                text(
                    """
                    SELECT
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.days_overdue
                    FROM invoices i
                    WHERE i.status IN ('open', 'overdue')
                    """
                )
            ).mappings().all()

        if not rows:
            return (
                self.DEFAULT_RECOVERY_PCT,
                self.DEFAULT_CASHFLOW,
                self.DEFAULT_DSO,
            )

        total_outstanding = sum(float(r["amount"] or 0.0) for r in rows)
        if total_outstanding <= 0:
            return (
                self.DEFAULT_RECOVERY_PCT,
                self.DEFAULT_CASHFLOW,
                self.DEFAULT_DSO,
            )

        weighted_recovery = 0.0
        weighted_expected_days = 0.0

        for r in rows:
            amount = float(r["amount"] or 0.0)
            days_overdue = int(r["days_overdue"] or 0)
            pay_30 = max(0.05, min(0.95, 1.0 - (days_overdue / 45.0)))
            expected_days = days_overdue + (1.0 - pay_30) * 30.0

            weighted_recovery += amount * pay_30
            weighted_expected_days += amount * expected_days

        baseline_recovery_pct = (weighted_recovery / total_outstanding) * 100.0
        baseline_cashflow = weighted_recovery
        baseline_dso = weighted_expected_days / total_outstanding
        return baseline_recovery_pct, baseline_cashflow, baseline_dso

    def simulate(self, request: WhatIfRequest) -> WhatIfResponse:
        """
        Apply scenario levers to baseline metrics and return projected impact.

        Modelling assumptions:
        - Each 1% efficiency gain → +0.8% recovery and proportional cashflow uplift
        - Each 1% discount offered → +1.2% recovery but discount haircut on cashflow
        - Each day earlier follow-up → −0.5 DSO days, +0.4% recovery
        """
        baseline_recovery, baseline_cashflow, baseline_dso = self._baseline_metrics()
        recovery = baseline_recovery
        cashflow = baseline_cashflow
        dso = baseline_dso

        # Efficiency lever
        eff = request.recovery_improvement_pct
        recovery += eff * 0.8
        cashflow += baseline_cashflow * (eff * 0.008)

        # Discount lever — attracts faster payment but reduces top-line
        disc = request.discount_pct
        recovery += disc * 1.2
        cashflow -= baseline_cashflow * (disc / 100)  # revenue haircut

        # Follow-up timing lever
        delay = request.delay_followup_days
        dso -= delay * 0.5          # earlier = lower DSO
        recovery += (-delay) * 0.4  # earlier = higher recovery

        # Cap realistic bounds
        recovery = min(100.0, max(0.0, recovery))
        dso = max(0.0, dso)

        scenario_parts = []
        if eff > 0:
            scenario_parts.append(f"+{eff:.0f}% collection efficiency")
        if disc > 0:
            scenario_parts.append(f"{disc:.0f}% early-pay discount")
        if delay != 0:
            direction = "earlier" if delay < 0 else "later"
            scenario_parts.append(f"follow-up {abs(delay)} days {direction}")

        summary = (
            "Baseline scenario — no changes applied."
            if not scenario_parts
            else "Scenario: " + ", ".join(scenario_parts) + "."
        )

        return WhatIfResponse(
            predicted_recovery_pct=round(recovery, 1),
            cashflow_shift=round(cashflow - baseline_cashflow, 2),
            dso_shift=round(dso - baseline_dso, 1),
            baseline_recovery_pct=round(baseline_recovery, 1),
            baseline_cashflow=round(baseline_cashflow, 2),
            baseline_dso=round(baseline_dso, 1),
            scenario_summary=summary,
        )
