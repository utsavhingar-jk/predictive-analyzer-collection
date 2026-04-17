"""
Invoice API routes backed by the canonical predictive portfolio payload.

Endpoints:
  GET /invoices              — paginated list of invoices with predictive fields
  GET /invoices/{invoice_id} — canonical invoice detail payload
  GET /invoices/summary      — portfolio-level summary metrics
"""

from fastapi import APIRouter, HTTPException

from app.services.portfolio_intelligence_service import PortfolioIntelligenceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])
portfolio_svc = PortfolioIntelligenceService()


@router.get("/summary", summary="Portfolio summary metrics")
async def get_summary() -> dict:
    """Return high-level AR portfolio metrics for the executive dashboard."""
    results = await portfolio_svc.build_portfolio_results()
    total_invoices = len(results)
    total_outstanding = sum(float(result.invoice["amount"]) for result in results)
    overdue_rows = [result for result in results if int(result.invoice["days_overdue"]) > 0]
    overdue_count = len(overdue_rows)
    overdue_amount = sum(float(result.invoice["amount"]) for result in overdue_rows)
    risk_breakdown = {"High": 0, "Medium": 0, "Low": 0}
    amount_at_risk = 0.0
    for result in results:
        amt = float(result.invoice["amount"])
        tier = result.delay.risk_tier
        risk_breakdown[tier] += 1
        if result.delay.delay_probability > 0.60:
            amount_at_risk += amt

    return {
        "total_invoices": int(total_invoices),
        "total_outstanding": float(total_outstanding),
        "overdue_count": int(overdue_count),
        "overdue_amount": float(overdue_amount),
        "amount_at_risk": float(amount_at_risk),
        "high_risk_count": int(risk_breakdown["High"]),
        "risk_breakdown": risk_breakdown,
    }


@router.get("/", summary="List all invoices")
async def list_invoices(
    status: str | None = None,
    risk: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return a filtered, paginated list of invoices from the canonical portfolio view."""
    results = await portfolio_svc.build_portfolio_results()

    if status:
        results = [result for result in results if result.invoice["status"] == status]
    if risk:
        results = [result for result in results if result.delay.risk_tier == risk]

    total = len(results)
    invoices = [result.as_invoice_list_item() for result in results[offset : offset + limit]]
    return {
        "total": total,
        "invoices": invoices,
        "canonical_payload_version": "portfolio-intelligence-v1",
    }


@router.get("/{invoice_id}", summary="Get invoice detail")
async def get_invoice(invoice_id: str) -> dict:
    """Return the canonical predictive payload for a single invoice."""
    results = await portfolio_svc.build_portfolio_results()
    match = next(
        (result for result in results if str(result.invoice["invoice_id"]) == str(invoice_id)),
        None,
    )
    if not match:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return match.as_invoice_detail()
