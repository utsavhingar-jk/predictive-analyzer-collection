"""
Payment Behavior Analysis API routes.

Endpoints:
  POST /analyze/payment-behavior  — classify borrower payment personality
  GET  /analyze/payment-behavior/{customer_id}  — behavior profile by customer
"""

from fastapi import APIRouter, HTTPException

from app.schemas.behavior import PaymentBehaviorRequest, PaymentBehaviorResponse
from app.services.behavior_service import BehaviorService
from app.utils.mock_data import MOCK_BEHAVIOR_PROFILES, get_behavior_by_customer_id

router = APIRouter(prefix="/analyze", tags=["Payment Behavior"])

behavior_svc = BehaviorService()


@router.post(
    "/payment-behavior",
    response_model=PaymentBehaviorResponse,
    summary="Analyze payment behavior",
    description=(
        "Classifies a borrower's payment personality based on historical payment patterns. "
        "Returns behavior type, trend, payment style, risk score, and NACH recommendation."
    ),
)
async def analyze_payment_behavior(
    request: PaymentBehaviorRequest,
) -> PaymentBehaviorResponse:
    return await behavior_svc.analyze(request)


@router.get(
    "/payment-behavior/{customer_id}",
    response_model=PaymentBehaviorResponse,
    summary="Get pre-computed behavior profile",
    description="Returns the pre-computed payment behavior profile for a known customer.",
)
def get_payment_behavior(customer_id: str) -> PaymentBehaviorResponse:
    profile = get_behavior_by_customer_id(customer_id)
    if not profile:
        raise HTTPException(
            status_code=404, detail=f"No behavior profile found for customer {customer_id}"
        )
    return PaymentBehaviorResponse(**profile)
