"""Collection prioritization service backed by the predictive portfolio pipeline."""

from app.schemas.prediction import PrioritizedInvoice
from app.services.portfolio_intelligence_service import PortfolioIntelligenceService


class PrioritizationService:
    def __init__(self) -> None:
        self.portfolio_svc = PortfolioIntelligenceService()

    async def get_prioritized_worklist(self) -> list[PrioritizedInvoice]:
        """Return the ranked collector worklist from the predictive portfolio engine."""
        return await self.portfolio_svc.get_prioritized_worklist()
