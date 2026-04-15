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
from app.utils.mock_data import MOCK_INVOICES

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
    portfolio_total = sum(
        inv["amount"] for inv in MOCK_INVOICES if inv["status"] in ("open", "overdue")
    )
    return borrower_svc.predict_borrower(request, portfolio_total=portfolio_total)


@router.get(
    "/borrowers/portfolio",
    response_model=list[BorrowerPortfolioItem],
    summary="Ranked borrower portfolio",
    description=(
        "Returns all borrowers ranked by borrower risk score descending. "
        "Each row includes exposure, delay probability, recovery rate, "
        "and escalation flag."
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
    # Build request from MOCK_INVOICES customer data
    customer_invoices = [
        inv for inv in MOCK_INVOICES
        if str(inv["customer_id"]) == customer_id
        and inv["status"] in ("open", "overdue")
    ]
    if not customer_invoices:
        raise HTTPException(
            status_code=404,
            detail=f"No open invoices found for customer {customer_id}",
        )

    sample = customer_invoices[0]
    portfolio_total = sum(
        inv["amount"] for inv in MOCK_INVOICES if inv["status"] in ("open", "overdue")
    )

    request = BorrowerPredictionRequest(
        customer_id=customer_id,
        customer_name=sample["customer_name"],
        industry=sample.get("industry", "unknown"),
        credit_score=sample.get("credit_score", 650),
        avg_days_to_pay=sample.get("avg_days_to_pay", 30.0),
        payment_terms=sample.get("payment_terms", 30),
        num_late_payments=sample.get("num_late_payments", 0),
    )
    return borrower_svc.predict_borrower(request, portfolio_total=portfolio_total)
