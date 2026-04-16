"""
Invoice API routes — portfolio overview and individual invoice detail.

Endpoints:
  GET /invoices              — paginated list of all invoices with predictions
  GET /invoices/{invoice_id} — full invoice detail with SHAP + recommendation
  GET /invoices/summary      — portfolio-level summary metrics
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.json_data import load_invoices_from_json
from app.services.risk_scoring import (
    build_amount_reference,
    delay_probability_from_score,
    risk_score,
    risk_tier_from_score,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("/summary", summary="Portfolio summary metrics")
def get_summary() -> dict:
    """Return high-level AR portfolio metrics for the executive dashboard."""
    try:
        with SessionLocal() as db:
            db_rows = db.execute(
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
        rows = [dict(r) for r in db_rows]
    except Exception as exc:
        logger.warning("get_summary: DB unavailable (%s) — using JSON fallback", exc)
        rows = load_invoices_from_json()

    total_invoices = len(rows)
    total_outstanding = sum(float(r["amount"] or 0) for r in rows)
    today = date.today()
    overdue_rows = [
        r for r in rows
        if str(r["status"]) == "overdue"
        or (str(r["status"]) == "open" and r.get("due_date") is not None and (
            r["due_date"] < today if isinstance(r["due_date"], date)
            else False
        ))
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
    try:
        with SessionLocal() as db:
            db_rows = db.execute(
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
        rows = [dict(r) for r in db_rows]
        for item in rows:
            for field in ("issue_date", "due_date"):
                if hasattr(item.get(field), "isoformat"):
                    item[field] = item[field].isoformat()
    except Exception as exc:
        logger.warning("list_invoices: DB unavailable (%s) — using JSON fallback", exc)
        raw = load_invoices_from_json()
        rows = []
        for r in raw:
            rows.append({
                **r,
                "due_date": r["due_date_str"],
                "risk_label": (
                    "High" if r["days_overdue"] >= 30 else
                    "Medium" if r["days_overdue"] >= 10 else "Low"
                ),
            })

    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in rows)
    invoices = []
    for item in rows:
        amount = float(item.get("amount") or 0)
        score = risk_score(int(item.get("days_overdue") or 0), amount, amount_reference)
        item["risk_score"] = round(score, 4)
        item["risk_label"] = risk_tier_from_score(score)
        invoices.append(item)
    if status:
        invoices = [i for i in invoices if i["status"] == status]
    if risk:
        invoices = [i for i in invoices if i.get("risk_label") == risk]
    total = len(invoices)
    return {"total": total, "invoices": invoices[offset: offset + limit]}


@router.get("/{invoice_id}", summary="Get invoice detail")
def get_invoice(invoice_id: str) -> dict:
    """Return full details for a single invoice including ML prediction metadata."""
    try:
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
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        logger.warning("get_invoice: DB unavailable (%s) — using JSON fallback", exc)
        raw_rows = load_invoices_from_json()
        match = next((r for r in raw_rows if str(r.get("invoice_id")) == str(invoice_id)), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        result = {"invoice_number": match.get("invoice_id"), "currency": "INR"}
        result.update(match)

    for field in ("issue_date", "due_date"):
        if hasattr(result.get(field), "isoformat"):
            result[field] = result[field].isoformat()

    days_overdue = int(result.get("days_overdue") or 0)
    amount = float(result.get("amount") or 0)

    try:
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
            invoices_for_ref = [{"amount": r["amount"]} for r in reference_rows]
    except Exception:
        invoices_for_ref = load_invoices_from_json()

    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in invoices_for_ref)
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
