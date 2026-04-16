"""
Invoice API routes — portfolio overview and individual invoice detail.

Endpoints:
  GET /invoices              — paginated list of all invoices with predictions
  GET /invoices/{invoice_id} — full invoice detail with SHAP + recommendation
  GET /invoices/summary      — portfolio-level summary metrics
"""

from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.risk_scoring import (
    build_amount_reference,
    delay_probability_from_score,
    risk_score,
    risk_tier_from_score,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/summary", summary="Portfolio summary metrics")
def get_summary() -> dict:
    """Return high-level AR portfolio metrics for the executive dashboard."""
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    COALESCE(outstanding_amount, amount) AS amount,
                    status,
                    due_date,
                    days_overdue
                FROM invoices
                WHERE status IN ('open', 'overdue')
                """
            )
        ).mappings().all()

    total_invoices = len(rows)
    total_outstanding = sum(float(r["amount"] or 0) for r in rows)
    today = date.today()
    overdue_rows = [
        r for r in rows
        if str(r["status"]) == "overdue"
        or (str(r["status"]) == "open" and r["due_date"] is not None and r["due_date"] < today)
    ]
    overdue_count = len(overdue_rows)
    overdue_amount = sum(float(r["amount"] or 0) for r in overdue_rows)

    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in rows)
    risk_breakdown = {"High": 0, "Medium": 0, "Low": 0}
    amount_at_risk = 0.0
    for r in rows:
        amt = float(r["amount"] or 0)
        score = risk_score(int(r["days_overdue"] or 0), amt, amount_reference)
        tier = risk_tier_from_score(score)
        risk_breakdown[tier] += 1
        if tier == "High":
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
def list_invoices(
    status: str | None = None,
    risk: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Return a filtered, paginated list of invoices."""
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    i.invoice_number AS invoice_id,
                    i.invoice_number,
                    i.customer_id,
                    c.name AS customer_name,
                    c.industry,
                    COALESCE(i.outstanding_amount, i.amount) AS amount,
                    i.currency,
                    i.issue_date,
                    i.due_date,
                    i.status,
                    i.days_overdue,
                    c.credit_score,
                    c.avg_days_to_pay,
                    c.num_late_payments,
                    CASE
                        WHEN i.days_overdue >= 30 THEN 'High'
                        WHEN i.days_overdue >= 10 THEN 'Medium'
                        ELSE 'Low'
                    END AS risk_label
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.status IN ('open', 'overdue')
                ORDER BY i.days_overdue DESC, i.due_date ASC
                """
            )
        ).mappings().all()

    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in rows)
    invoices = []
    for row in rows:
        item = dict(row)
        amount = float(item.get("amount") or 0)
        score = risk_score(int(item.get("days_overdue") or 0), amount, amount_reference)
        item["risk_score"] = round(score, 4)
        item["risk_label"] = risk_tier_from_score(score)
        for field in ("issue_date", "due_date"):
            if hasattr(item.get(field), "isoformat"):
                item[field] = item[field].isoformat()
        invoices.append(item)
    if status:
        invoices = [i for i in invoices if i["status"] == status]
    if risk:
        invoices = [i for i in invoices if i.get("risk_label") == risk]
    total = len(invoices)
    return {"total": total, "invoices": invoices[offset : offset + limit]}


@router.get("/{invoice_id}", summary="Get invoice detail")
def get_invoice(invoice_id: str) -> dict:
    """Return full details for a single invoice including ML prediction metadata."""
    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT
                    i.invoice_number AS invoice_id,
                    i.invoice_number,
                    i.customer_id,
                    c.name AS customer_name,
                    c.industry,
                    COALESCE(i.outstanding_amount, i.amount) AS amount,
                    i.currency,
                    i.issue_date,
                    i.due_date,
                    i.status,
                    i.days_overdue,
                    c.credit_score,
                    c.avg_days_to_pay,
                    c.num_late_payments,
                    CASE
                        WHEN i.days_overdue >= 30 THEN 'High'
                        WHEN i.days_overdue >= 10 THEN 'Medium'
                        ELSE 'Low'
                    END AS risk_label
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.invoice_number = :invoice_id
                LIMIT 1
                """
            ),
            {"invoice_id": invoice_id},
        ).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    result = dict(row)
    for field in ("issue_date", "due_date"):
        if hasattr(result.get(field), "isoformat"):
            result[field] = result[field].isoformat()

    days_overdue = int(result.get("days_overdue") or 0)
    amount = float(result.get("amount") or 0)

    with SessionLocal() as db:
        reference_rows = db.execute(
            text(
                """
                SELECT COALESCE(outstanding_amount, amount) AS amount
                FROM invoices
                WHERE status IN ('open', 'overdue')
                """
            )
        ).mappings().all()
    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in reference_rows)
    combined_score = risk_score(days_overdue, amount, amount_reference)
    delay_probability = delay_probability_from_score(combined_score)
    pay_30 = round(1.0 - delay_probability, 4)
    pay_15 = round(max(0.01, pay_30 * 0.7), 4)
    pay_7 = round(max(0.01, pay_30 * 0.4), 4)
    risk_tier = risk_tier_from_score(combined_score)
    urgency = "Critical" if days_overdue >= 45 else "High" if days_overdue >= 20 else "Medium"
    recommended_action = (
        "Escalate relationship and collector follow-up"
        if days_overdue >= 45
        else "Collection call and payment plan follow-up"
        if days_overdue >= 20
        else "Reminder sequence"
    )
    top_drivers: list[str] = []
    if days_overdue > 0:
        top_drivers.append(f"{days_overdue} days overdue")
    if result.get("num_late_payments") is not None:
        top_drivers.append(f"{int(result['num_late_payments'])} historical late payments")
    if result.get("credit_score") is not None:
        top_drivers.append(f"Credit score {int(result['credit_score'])}")

    result["pay_7_days"] = pay_7
    result["pay_15_days"] = pay_15
    result["pay_30_days"] = pay_30
    result["risk_label"] = risk_tier
    result["risk_score"] = int(round(combined_score * 100))
    result["recommended_action"] = recommended_action
    result["delay_prediction"] = {
        "invoice_id": result["invoice_id"],
        "delay_probability": round(delay_probability, 4),
        "risk_score": int(round(delay_probability * 100)),
        "risk_tier": risk_tier,
        "top_drivers": top_drivers,
        "model_version": "db-rule-v1",
    }
    result["strategy"] = {
        "invoice_id": result["invoice_id"],
        "priority_score": int(round(float(result["amount"]) * delay_probability / max(float(result["amount"]), 1.0) * 100)),
        "recommended_action": recommended_action,
        "urgency": urgency,
        "channel": "Call",
        "reason": f"Delay probability {round(delay_probability*100)}% with {days_overdue} DPD and {risk_tier} risk tier.",
        "automation_flag": days_overdue < 20,
        "next_action_in_hours": 8 if days_overdue >= 45 else 24,
    }
    return result
