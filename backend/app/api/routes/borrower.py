"""
Borrower-Level Prediction API routes.

Endpoints:
  POST /predict/borrower              — full borrower-level prediction from request body
  GET  /predict/borrower/{customer_id}— prediction for a known customer (auto-populated)
  GET  /predict/borrowers/portfolio   — ranked portfolio view of all borrowers
"""

from fastapi import APIRouter, HTTPException

from app.schemas.borrower import (
    BorrowerPortfolioItem,
    BorrowerPredictionRequest,
    BorrowerPredictionResponse,
)
from app.services.borrower_service import BorrowerService

router = APIRouter(prefix="/predict", tags=["Borrower Prediction"])

borrower_svc = BorrowerService()


@router.post(
    "/borrower",
    response_model=BorrowerPredictionResponse,
    summary="Borrower-level risk prediction",
    description=(
        "Aggregates all open invoices for a borrower and computes: "
        "weighted delay probability, borrower risk score, expected recovery, "
        "at-risk amount, DSO vs benchmark, and relationship-level action."
    ),
)
def predict_borrower(request: BorrowerPredictionRequest) -> BorrowerPredictionResponse:
    portfolio_total = borrower_svc.get_portfolio_total_outstanding()
    return borrower_svc.predict_borrower(request, portfolio_total=portfolio_total)


@router.get(
    "/borrowers/portfolio",
    response_model=list[BorrowerPortfolioItem],
    summary="Ranked borrower portfolio",
    description=(
        "Returns all borrowers ranked by borrower risk score descending. "
        "Each row includes exposure, delay probability, recovery rate, "
        "and escalation flag. "
        "Blends ML-service output with backend rule scores (BORROWER_PORTFOLIO_HYBRID_ML_WEIGHT, "
        "default 0.5); relationship actions follow backend rules. "
        "Batch ML call (POST /predict/borrowers/portfolio) with no OpenAI; "
        "falls back to parallel per-borrower ML if batch fails."
    ),
)
def get_borrower_portfolio() -> list[BorrowerPortfolioItem]:
    return borrower_svc.get_portfolio_borrowers()


@router.get(
    "/borrower/{customer_id}",
    response_model=BorrowerPredictionResponse,
    summary="Borrower prediction by customer ID",
    description="Looks up all open invoices for the customer and returns full borrower prediction.",
)
def get_borrower_prediction(customer_id: str) -> BorrowerPredictionResponse:
    request = borrower_svc.get_borrower_request_by_customer_id(customer_id)
    if not request:
        raise HTTPException(
            status_code=404,
            detail=f"No open invoices found for customer {customer_id}",
        )
    portfolio_total = borrower_svc.get_portfolio_total_outstanding()
    return borrower_svc.predict_borrower(request, portfolio_total=portfolio_total)
