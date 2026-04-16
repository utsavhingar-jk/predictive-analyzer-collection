"""
Sentinel External Signals API routes.

Endpoints:
  GET /sentinel/check/{customer_id} — external signals for a customer
  GET /sentinel/watchlist           — all flagged customers
"""

from fastapi import APIRouter

from app.schemas.sentinel import SentinelCheckResponse, WatchlistResponse
from app.services.sentinel_service import SentinelService

router = APIRouter(prefix="/sentinel", tags=["Sentinel Watchlist"])

_svc = SentinelService()


@router.get(
    "/check/{customer_id}",
    response_model=SentinelCheckResponse,
    summary="Check external signals for a customer",
)
def check_customer(customer_id: str) -> SentinelCheckResponse:
    """Return Sentinel external risk signals for the given customer."""
    return _svc.check_customer(customer_id)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    summary="Sentinel watchlist — all flagged customers",
)
def get_watchlist() -> WatchlistResponse:
    """Return all customers with active Sentinel risk flags, sorted by severity."""
    return _svc.get_watchlist()
