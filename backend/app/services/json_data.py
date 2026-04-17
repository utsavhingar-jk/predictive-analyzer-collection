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


def _stable_customer_id(inv: dict) -> str:
    """
    Prefer business-facing borrower identifiers from the JSON payload.

    The sample JSON can reuse internal Mongo-style `id` values across different
    borrowers, which causes cross-borrower leakage in portfolio grouping and
    agent context. Public IDs are stable across invoices and remain readable in
    the UI/debug traces, so they are the safest fallback identifier here.
    """
    borrower = inv.get("borrower") or {}
    raised_against = inv.get("invoiceRaisedAgainstUser") or {}
    payee = inv.get("payee") or {}

    for candidate in (
        borrower.get("publicId"),
        raised_against.get("publicId"),
        payee.get("publicId"),
        borrower.get("id"),
        raised_against.get("id"),
        payee.get("id"),
        borrower.get("name"),
        raised_against.get("name"),
    ):
        if candidate:
            return str(candidate)
    return str(inv.get("invoiceNumber") or inv.get("id") or "")


def _find_invoices_json() -> Path | None:
    """Search multiple candidate paths for invoices.json."""
    this_file = Path(__file__).resolve()

    candidates = [
        # Docker: WORKDIR /app, COPY backend/ . → /app/data/invoices.json
        this_file.parents[2] / "data" / "invoices.json",
        # Native Render / local: repo root data/
        this_file.parents[3] / "data" / "invoices.json",
        # Absolute fallback — common Render native path
        Path("/opt/render/project/src/data/invoices.json"),
        Path("/opt/render/project/src/backend/data/invoices.json"),
    ]
    for p in candidates:
        if p.exists():
            logger.info("json_data: found invoices.json at %s", p)
            return p

    logger.error("json_data: invoices.json not found. Tried: %s", [str(c) for c in candidates])
    return None


def load_invoices_from_json() -> list[dict]:
    """
    Parse data/invoices.json and return a list of normalized invoice dicts.
    """
    today = date.today()
    json_path = _find_invoices_json()

    if json_path is None:
        return []

    try:
        with open(json_path, "r") as f:
            raw: list[dict] = json.load(f)
    except Exception as exc:
        logger.error("json_data: failed to load %s: %s", json_path, exc)
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
        customer_id = _stable_customer_id(inv)

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

    logger.info("json_data: loaded %d invoices from %s", len(rows), json_path)
    return rows
