"""
Collection Strategy Optimization API routes.

Endpoints:
  POST /optimize/collection-strategy  — compute optimised collection action + priority
  GET  /optimize/portfolio-strategy   — strategy for all open invoices with portfolio ranking
"""

from fastapi import APIRouter

from app.schemas.strategy import StrategyRequest, StrategyResponse
from app.services.portfolio_intelligence_service import PortfolioIntelligenceService
from app.services.strategy_service import StrategyService

router = APIRouter(prefix="/optimize", tags=["Collection Strategy"])

strategy_svc = StrategyService()
portfolio_svc = PortfolioIntelligenceService()


@router.post(
    "/collection-strategy",
    response_model=StrategyResponse,
    summary="Optimize collection strategy for an invoice",
    description=(
        "Takes delay risk, invoice signals, and behavior type to return a "
        "priority score, urgency, recommended action, and collection channel."
    ),
)
def optimize_strategy(request: StrategyRequest) -> StrategyResponse:
    return strategy_svc.optimize(request)


@router.get(
    "/portfolio-strategy",
    response_model=list[StrategyResponse],
    summary="Priority-ranked strategy for entire portfolio",
    description="Computes and ranks collection strategies for all open invoices in the portfolio.",
)
async def get_portfolio_strategy() -> list[StrategyResponse]:
    return await portfolio_svc.get_portfolio_strategies()
