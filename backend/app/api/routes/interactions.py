"""
Collections Interaction History API routes.

Endpoints:
  GET /interactions/{invoice_id}   — full history + effectiveness for one invoice
  GET /interactions/portfolio/effectiveness — portfolio-wide action analytics
"""

from fastapi import APIRouter

from app.schemas.interaction import InteractionHistoryResponse
from app.services.interaction_service import InteractionService

router = APIRouter(prefix="/interactions", tags=["Interaction History"])

_svc = InteractionService()


@router.get(
    "/{invoice_id}",
    response_model=InteractionHistoryResponse,
    summary="Interaction history + action effectiveness for an invoice",
)
def get_invoice_interactions(invoice_id: str) -> InteractionHistoryResponse:
    """Return all collection touchpoints and effectiveness analytics for the given invoice."""
    return _svc.get_by_invoice(invoice_id)


@router.get(
    "/portfolio/effectiveness",
    summary="Portfolio-wide action effectiveness analytics",
)
def portfolio_effectiveness() -> dict:
    """Return which collection actions work best across the entire portfolio."""
    return _svc.get_portfolio_effectiveness()
