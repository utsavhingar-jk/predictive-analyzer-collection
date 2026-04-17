"""What-if scenario simulation anchored to predictive portfolio baselines."""

from app.schemas.whatif import WhatIfRequest, WhatIfResponse
from app.services.portfolio_intelligence_service import PortfolioIntelligenceService


class WhatIfService:
    DEFAULT_RECOVERY_PCT: float = 68.0
    DEFAULT_DSO: float = 45.0
    DEFAULT_CASHFLOW: float = 0.0

    def __init__(self) -> None:
        self.portfolio_svc = PortfolioIntelligenceService()

    async def _baseline_metrics(self) -> tuple[float, float, float]:
        results = await self.portfolio_svc.build_portfolio_results()
        if not results:
            return (
                self.DEFAULT_RECOVERY_PCT,
                self.DEFAULT_CASHFLOW,
                self.DEFAULT_DSO,
            )

        total_outstanding = sum(float(result.invoice["amount"]) for result in results)
        if total_outstanding <= 0:
            return (
                self.DEFAULT_RECOVERY_PCT,
                self.DEFAULT_CASHFLOW,
                self.DEFAULT_DSO,
            )

        baseline_cashflow = sum(
            float(result.invoice["amount"]) * float(result.payment.pay_30_days)
            for result in results
        )
        baseline_recovery_pct = (baseline_cashflow / total_outstanding) * 100.0
        baseline_dso = sum(
            float(result.invoice["amount"]) * result.predicted_collection_age_days()
            for result in results
        ) / total_outstanding
        return baseline_recovery_pct, baseline_cashflow, baseline_dso

    async def simulate(self, request: WhatIfRequest) -> WhatIfResponse:
        """
        Apply scenario levers to predictive baseline metrics and return projected impact.

        Modelling assumptions:
        - Each 1% efficiency gain -> +0.8% recovery and proportional cashflow uplift
        - Each 1% discount offered -> +1.2% recovery but discount haircut on cashflow
        - Each day earlier follow-up -> -0.5 DSO days, +0.4% recovery
        """
        baseline_recovery, baseline_cashflow, baseline_dso = await self._baseline_metrics()
        recovery = baseline_recovery
        cashflow = baseline_cashflow
        dso = baseline_dso

        eff = request.recovery_improvement_pct
        recovery += eff * 0.8
        cashflow += baseline_cashflow * (eff * 0.008)

        disc = request.discount_pct
        recovery += disc * 1.2
        cashflow -= baseline_cashflow * (disc / 100)

        delay = request.delay_followup_days
        dso -= delay * 0.5
        recovery += (-delay) * 0.4

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
