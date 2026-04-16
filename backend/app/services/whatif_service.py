"""
What-If scenario simulation service.

Allows collectors and managers to model the impact of strategy changes
(efficiency improvements, discounts, follow-up timing shifts) on key AR metrics.
"""

from app.schemas.whatif import WhatIfRequest, WhatIfResponse
from app.utils.mock_data import MOCK_INVOICES


class WhatIfService:
    # Baseline assumptions derived from mock portfolio
    BASELINE_RECOVERY_PCT: float = 68.0    # % of outstanding recovered in 30 days
    BASELINE_DSO: float = 48.5
    BASELINE_CASHFLOW: float = 22_000_000.0  # ₹ 30-day expected inflow (68% of ~₹3.2Cr portfolio)

    def simulate(self, request: WhatIfRequest) -> WhatIfResponse:
        """
        Apply scenario levers to baseline metrics and return projected impact.

        Modelling assumptions:
        - Each 1% efficiency gain → +0.8% recovery and +₹1,76,000 cashflow
        - Each 1% discount offered → +1.2% recovery but −1% cashflow (net)
        - Each day earlier follow-up → −0.5 DSO days, +0.4% recovery
        """
        recovery = self.BASELINE_RECOVERY_PCT
        cashflow = self.BASELINE_CASHFLOW
        dso = self.BASELINE_DSO

        # Efficiency lever
        eff = request.recovery_improvement_pct
        recovery += eff * 0.8
        cashflow += eff * 176_000

        # Discount lever — attracts faster payment but reduces top-line
        disc = request.discount_pct
        recovery += disc * 1.2
        cashflow -= cashflow * (disc / 100)  # revenue haircut

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
            cashflow_shift=round(cashflow - self.BASELINE_CASHFLOW, 2),
            dso_shift=round(dso - self.BASELINE_DSO, 1),
            baseline_recovery_pct=self.BASELINE_RECOVERY_PCT,
            baseline_cashflow=self.BASELINE_CASHFLOW,
            baseline_dso=self.BASELINE_DSO,
            scenario_summary=summary,
        )
