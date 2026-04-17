"""Predictive DSO service driven by portfolio payment forecasts."""

from app.schemas.prediction import DSOPredictionResponse
from app.services.portfolio_intelligence_service import PortfolioIntelligenceService


class DSOService:
    def __init__(self) -> None:
        self.portfolio_svc = PortfolioIntelligenceService()

    async def predict_dso(self) -> DSOPredictionResponse:
        results = await self.portfolio_svc.build_portfolio_results()
        if not results:
            return DSOPredictionResponse(
                predicted_dso=45.0,
                current_dso=45.0,
                dso_trend="stable",
                benchmark_dso=45.0,
            )

        total_outstanding = sum(float(result.invoice["amount"]) for result in results)
        current_dso = sum(
            float(result.invoice["amount"]) * result.current_age_days()
            for result in results
        ) / max(total_outstanding, 1.0)
        predicted_dso = sum(
            float(result.invoice["amount"]) * result.predicted_collection_age_days()
            for result in results
        ) / max(total_outstanding, 1.0)
        benchmark_dso = sum(
            float(result.invoice["amount"]) * float(result.invoice["payment_terms"])
            for result in results
        ) / max(total_outstanding, 1.0)

        if predicted_dso < current_dso * 0.97:
            trend = "improving"
        elif predicted_dso > current_dso * 1.03:
            trend = "worsening"
        else:
            trend = "stable"

        return DSOPredictionResponse(
            predicted_dso=round(predicted_dso, 1),
            current_dso=round(current_dso, 1),
            dso_trend=trend,
            benchmark_dso=round(benchmark_dso, 1),
        )
