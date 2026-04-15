"""
Invoice API routes — portfolio overview and individual invoice detail.

Endpoints:
  GET /invoices              — paginated list of all invoices with predictions
  GET /invoices/{invoice_id} — full invoice detail with SHAP + recommendation
  GET /invoices/summary      — portfolio-level summary metrics
"""

from fastapi import APIRouter, HTTPException

from app.utils.mock_data import MOCK_INVOICES, get_invoice_by_id, get_portfolio_summary

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/summary", summary="Portfolio summary metrics")
def get_summary() -> dict:
    """Return high-level AR portfolio metrics for the executive dashboard."""
    return get_portfolio_summary()


@router.get("/", summary="List all invoices")
def list_invoices(
    status: str | None = None,
    risk: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return a filtered, paginated list of invoices."""
    invoices = MOCK_INVOICES

    if status:
        invoices = [i for i in invoices if i["status"] == status]
    if risk:
        invoices = [i for i in invoices if i.get("risk_label") == risk]

    total = len(invoices)
    page = invoices[offset : offset + limit]

    return {"total": total, "invoices": page}


@router.get("/{invoice_id}", summary="Get invoice detail")
def get_invoice(invoice_id: str) -> dict:
    """Return full details for a single invoice including ML prediction metadata."""
    inv = get_invoice_by_id(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    # Serialize dates to ISO strings for JSON compatibility
    result = {**inv}
    for field in ("issue_date", "due_date"):
        if hasattr(result.get(field), "isoformat"):
            result[field] = result[field].isoformat()

    return result
