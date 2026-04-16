"""
Shared JSON data loader — fallback when the database is unavailable.

Loads from data/invoices.json (committed in the repo root) and returns
rows in a normalized dict format compatible with all backend services.
"""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root: backend/app/services/ → 3 levels up → repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_INVOICES_JSON = _REPO_ROOT / "data" / "invoices.json"


def load_invoices_from_json() -> list[dict]:
    """
    Parse data/invoices.json and return a list of normalized invoice dicts.

    Computed fields:
      - days_overdue: max(0, today − invoiceDueDate)
      - status: 'overdue' if days_overdue > 0 else 'open'
    """
    today = date.today()

    try:
        with open(_INVOICES_JSON, "r") as f:
            raw: list[dict] = json.load(f)
    except FileNotFoundError:
        logger.error("invoices.json not found at %s", _INVOICES_JSON)
        return []

    rows: list[dict] = []
    for inv in raw:
        due_str = inv.get("invoiceDueDate") or ""
        try:
            due_date = date.fromisoformat(due_str) if due_str else today
        except ValueError:
            due_date = today

        issue_str = inv.get("invoiceDate") or ""
        try:
            issue_date = date.fromisoformat(issue_str) if issue_str else today
        except ValueError:
            issue_date = today

        days_overdue = max(0, (today - due_date).days)
        status = "overdue" if days_overdue > 0 else "open"
        amount = float(inv.get("invoiceAmount") or inv.get("loanAmount") or 0)
        customer_name = (
            (inv.get("borrower") or {}).get("name")
            or (inv.get("invoiceRaisedAgainstUser") or {}).get("name")
            or "Unknown Customer"
        )
        invoice_id = inv.get("invoiceNumber") or inv.get("id") or ""
        customer_id = (inv.get("borrower") or {}).get("id") or invoice_id

        rows.append({
            "invoice_id":       invoice_id,
            "invoice_number":   invoice_id,
            "customer_id":      customer_id,
            "customer_name":    customer_name,
            "industry":         "unknown",
            "amount":           amount,
            "currency":         "INR",
            "issue_date":       issue_date.isoformat(),
            "due_date":         due_date,           # kept as date for services
            "due_date_str":     due_date.isoformat(),
            "status":           status,
            "days_overdue":     days_overdue,
            "nach_applicable":  False,
            # Sensible defaults (not in JSON)
            "credit_score":     650,
            "avg_days_to_pay":  30.0,
            "num_late_payments": max(0, days_overdue // 15),
        })

    logger.info("json_data: loaded %d invoices from %s", len(rows), _INVOICES_JSON)
    return rows
