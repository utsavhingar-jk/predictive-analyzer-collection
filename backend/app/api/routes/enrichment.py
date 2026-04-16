"""
Borrower Enrichment (CredCheck) API routes.

Endpoints:
  GET /enrichment/{customer_id}   — MCA/GST/EPFO/bureau/legal profile
"""

from fastapi import APIRouter

from app.schemas.enrichment import BorrowerEnrichmentResponse
from app.services.enrichment_service import EnrichmentService

router = APIRouter(prefix="/enrichment", tags=["Borrower Enrichment"])

_svc = EnrichmentService()


@router.get(
    "/{customer_id}",
    response_model=BorrowerEnrichmentResponse,
    summary="CredCheck enrichment profile for a borrower",
)
def get_enrichment(customer_id: str) -> BorrowerEnrichmentResponse:
    """Return MCA compliance, GST health, EPFO stability, bureau, and legal profile."""
    return _svc.get_enrichment(customer_id)
