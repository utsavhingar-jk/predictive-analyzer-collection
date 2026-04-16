"""
Collection Strategy Optimization API routes.

Endpoints:
  POST /optimize/collection-strategy  — compute optimised collection action + priority
  GET  /optimize/portfolio-strategy   — strategy for all open invoices with portfolio ranking
"""

from fastapi import APIRouter

from app.schemas.strategy import StrategyRequest, StrategyResponse
from app.services.strategy_service import StrategyService
from app.utils.mock_data import MOCK_INVOICES, MOCK_BEHAVIOR_PROFILES

router = APIRouter(prefix="/optimize", tags=["Collection Strategy"])

strategy_svc = StrategyService()


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
def get_portfolio_strategy() -> list[StrategyResponse]:
    strategies: list[StrategyResponse] = []

    for inv in MOCK_INVOICES:
        if inv["status"] not in ("open", "overdue"):
            continue

        # Fetch pre-computed behavior profile if available
        behavior = next(
            (b for b in MOCK_BEHAVIOR_PROFILES if b["customer_id"] == str(inv["customer_id"])),
            None,
        )
        behavior_type = behavior["behavior_type"] if behavior else None
        followup_dep = behavior.get("followup_dependency", False) if behavior else False
        nach = behavior.get("nach_recommended", False) if behavior else False

        delay_prob = 1.0 - inv.get("pay_30_days", 0.5)
        risk_tier = inv.get("risk_label", "Medium")

        req = StrategyRequest(
            invoice_id=inv["invoice_id"],
            customer_name=inv["customer_name"],
            invoice_amount=inv["amount"],
            days_overdue=inv.get("days_overdue", 0),
            delay_probability=delay_prob,
            risk_tier=risk_tier,
            nach_applicable=nach,
            behavior_type=behavior_type,
            followup_dependency=followup_dep,
        )
        result = strategy_svc.optimize(req)

        # Enrich with invoice fields needed for the worklist table
        result.customer_name = inv["customer_name"]
        result.amount = inv["amount"]
        result.days_overdue = inv.get("days_overdue", 0)
        result.risk_label = inv.get("risk_label", "Medium")
        result.risk_tier = inv.get("risk_label", "Medium")
        result.delay_probability = round(delay_prob, 4)
        result.behavior_type = behavior_type
        result.nach_recommended = nach

        strategies.append(result)

    return strategy_svc.rank_portfolio(strategies)
