"""
Load real JSON data into customers, invoices, and payment_transactions.

Usage:
    cd backend
    python scripts/load_real_data.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"


@dataclass
class CustomerSeed:
    external_id: str
    name: str
    payment_terms: int = 30
    avg_days_to_pay: float = 0.0
    total_overdue: float = 0.0
    num_late_payments: int = 0
    credit_score: int = 650


def _read_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, dict):
        iso_val = value.get("$date")
        if isinstance(iso_val, str):
            return _parse_date(iso_val)
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = cleaned.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            try:
                return datetime.strptime(cleaned.split(" ")[0], "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _build_customer_map(
    clients: list[dict[str, Any]], invoices: list[dict[str, Any]]
) -> dict[str, CustomerSeed]:
    customer_map: dict[str, CustomerSeed] = {}

    def ensure_customer(external_id: str, name: str, payment_terms: int = 30) -> None:
        ext = external_id.strip()
        if ext in customer_map:
            # Keep highest observed payment terms.
            if payment_terms > customer_map[ext].payment_terms:
                customer_map[ext].payment_terms = payment_terms
            return
        customer_map[ext] = CustomerSeed(
            external_id=ext,
            name=name.strip() or ext,
            payment_terms=payment_terms,
        )

    for client in clients:
        ext = str(client.get("clientId") or client.get("corporateRefId") or "").strip()
        if not ext:
            continue
        name = str(client.get("legalName") or client.get("businessName") or ext)
        ensure_customer(ext, name)

    for inv in invoices:
        borrower = inv.get("borrower") or {}
        raised_against = inv.get("invoiceRaisedAgainstUser") or {}
        ext = str(
            borrower.get("publicId")
            or raised_against.get("publicId")
            or inv.get("invoiceRaisedAgainst")
            or ""
        ).strip()
        if not ext:
            continue
        name = str(
            borrower.get("name")
            or raised_against.get("name")
            or inv.get("customerName")
            or ext
        )
        terms = _to_int((inv.get("creditDetails") or {}).get("creditPeriod"), default=30)
        ensure_customer(ext, name, payment_terms=max(1, terms))

    return customer_map


def main() -> None:
    clients = _read_json_records(DATA_DIR / "clients.json")
    invoices_raw = _read_json_records(DATA_DIR / "invoices.json")
    repayments_raw = _read_json_records(DATA_DIR / "repayments.json")

    if not invoices_raw:
        raise RuntimeError("No invoice data found in data/invoices.json")

    customers = _build_customer_map(clients, invoices_raw)

    today = date.today()
    invoice_rows: list[dict[str, Any]] = []
    invoice_credit_plan_by_number: dict[str, str] = {}

    for inv in invoices_raw:
        invoice_number = str(inv.get("invoiceNumber") or "").strip()
        if not invoice_number:
            continue

        borrower = inv.get("borrower") or {}
        raised_against = inv.get("invoiceRaisedAgainstUser") or {}
        customer_external_id = str(
            borrower.get("publicId")
            or raised_against.get("publicId")
            or inv.get("invoiceRaisedAgainst")
            or ""
        ).strip()
        if not customer_external_id:
            continue

        issue_date = _parse_date(inv.get("invoiceDate")) or today
        due_date = _parse_date(inv.get("invoiceDueDate")) or issue_date
        amount = _to_float(inv.get("invoiceAmount") or inv.get("loanAmount"), default=0.0)
        if amount <= 0:
            continue

        credit_plan_key = str(
            borrower.get("creditPlanPublicId")
            or borrower.get("creditPlanId")
            or (inv.get("anchor") or {}).get("creditPlanPublicId")
            or ""
        ).strip()
        days_overdue = max((today - due_date).days, 0)
        status = "overdue" if days_overdue > 0 else "open"
        source_invoice_id = str(inv.get("id") or "").strip()
        notes_payload = {
            "source_invoice_id": source_invoice_id or None,
            "source_invoice_ref": str(inv.get("invoiceRefNumber") or "").strip() or None,
            "source_credit_plan_id": credit_plan_key or None,
        }

        invoice_rows.append(
            {
                "invoice_number": invoice_number,
                "customer_external_id": customer_external_id,
                "amount": amount,
                "currency": "INR",
                "issue_date": issue_date,
                "due_date": due_date,
                "status": status,
                "days_overdue": days_overdue,
                "outstanding_amount": amount,
                "nach_applicable": False,
                "notes": _json_text(notes_payload),
            }
        )
        if credit_plan_key:
            invoice_credit_plan_by_number[invoice_number] = credit_plan_key

    if not invoice_rows:
        raise RuntimeError("No valid invoice rows were mapped from data/invoices.json")

    with SessionLocal() as db:
        # Upsert customers.
        for seed in customers.values():
            db.execute(
                text(
                    """
                    INSERT INTO customers (
                        external_id, name, industry, borrower_type, credit_score,
                        payment_terms, avg_days_to_pay, total_overdue, num_late_payments
                    ) VALUES (
                        :external_id, :name, :industry, :borrower_type, :credit_score,
                        :payment_terms, :avg_days_to_pay, :total_overdue, :num_late_payments
                    )
                    ON CONFLICT (external_id) DO UPDATE
                    SET
                        name = EXCLUDED.name,
                        payment_terms = EXCLUDED.payment_terms,
                        updated_at = NOW()
                    """
                ),
                {
                    "external_id": seed.external_id,
                    "name": seed.name,
                    "industry": "Unknown",
                    "borrower_type": "corporate",
                    "credit_score": seed.credit_score,
                    "payment_terms": seed.payment_terms,
                    "avg_days_to_pay": seed.avg_days_to_pay,
                    "total_overdue": seed.total_overdue,
                    "num_late_payments": seed.num_late_payments,
                },
            )

        db.flush()

        external_ids = list(customers.keys())
        customer_id_lookup = {
            row.external_id: int(row.id)
            for row in db.execute(
                text(
                    """
                    SELECT id, external_id
                    FROM customers
                    WHERE external_id = ANY(:external_ids)
                    """
                ),
                {"external_ids": external_ids},
            ).fetchall()
        }

        # Upsert invoices.
        normalized_invoice_rows: list[dict[str, Any]] = []
        for inv in invoice_rows:
            customer_id = customer_id_lookup.get(inv["customer_external_id"])
            if customer_id is None:
                continue
            normalized_invoice_rows.append(
                {
                    "invoice_number": inv["invoice_number"],
                    "customer_id": customer_id,
                    "amount": inv["amount"],
                    "currency": inv["currency"],
                    "issue_date": inv["issue_date"],
                    "due_date": inv["due_date"],
                    "status": inv["status"],
                    "days_overdue": inv["days_overdue"],
                    "outstanding_amount": inv["outstanding_amount"],
                    "nach_applicable": inv["nach_applicable"],
                    "notes": inv["notes"],
                }
            )

        for inv in normalized_invoice_rows:
            db.execute(
                text(
                    """
                    INSERT INTO invoices (
                        invoice_number, customer_id, amount, currency,
                        issue_date, due_date, status, days_overdue,
                        outstanding_amount, nach_applicable, notes
                    ) VALUES (
                        :invoice_number, :customer_id, :amount, :currency,
                        :issue_date, :due_date, :status, :days_overdue,
                        :outstanding_amount, :nach_applicable, :notes
                    )
                    ON CONFLICT (invoice_number) DO UPDATE
                    SET
                        customer_id = EXCLUDED.customer_id,
                        amount = EXCLUDED.amount,
                        issue_date = EXCLUDED.issue_date,
                        due_date = EXCLUDED.due_date,
                        status = EXCLUDED.status,
                        days_overdue = EXCLUDED.days_overdue,
                        outstanding_amount = EXCLUDED.outstanding_amount,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """
                ),
                inv,
            )

        db.flush()

        invoice_pk_by_number = {
            row.invoice_number: row.id
            for row in db.execute(
                text("SELECT id, invoice_number FROM invoices WHERE invoice_number = ANY(:nums)"),
                {"nums": [inv["invoice_number"] for inv in normalized_invoice_rows]},
            ).fetchall()
        }
        invoice_customer_by_pk = {
            int(row.id): int(row.customer_id)
            for row in db.execute(
                text("SELECT id, customer_id FROM invoices WHERE invoice_number = ANY(:nums)"),
                {"nums": [inv["invoice_number"] for inv in normalized_invoice_rows]},
            ).fetchall()
        }
        invoice_pk_by_credit_plan = {
            credit_plan_id: invoice_pk_by_number[inv_num]
            for inv_num, credit_plan_id in invoice_credit_plan_by_number.items()
            if inv_num in invoice_pk_by_number
        }
        invoices_by_customer: dict[int, list[int]] = {}
        for pk, c_id in invoice_customer_by_pk.items():
            invoices_by_customer.setdefault(c_id, []).append(pk)

        # Insert payment transactions.
        inserted_transactions = 0
        linked_by_invoice_key = 0
        linked_by_credit_plan = 0
        linked_by_customer_fallback = 0
        unresolved_links = 0
        for repayment in repayments_raw:
            parent_customer_ext = str(
                repayment.get("channelPartnerId") or repayment.get("partner") or ""
            ).strip()
            parent_customer_id = customer_id_lookup.get(parent_customer_ext)
            repayment_credit_plan_id = str(repayment.get("creditPlanId") or "").strip()
            repayment_ar_ids = [
                str(x).strip() for x in (repayment.get("arIds") or []) if str(x).strip()
            ]

            payment_date = _parse_date(
                repayment.get("transactionDate") or repayment.get("paymentCreatedOn")
            ) or today
            payment_mode = str(repayment.get("paymentMethod") or "MANUAL_UPDATE")
            status = str(repayment.get("status") or "SUCCESS").lower()
            txn_ref = str(repayment.get("transactionUtr") or repayment.get("repaymentId") or "")

            child_transactions = repayment.get("childTransactions") or []
            if not child_transactions:
                child_transactions = [
                    {
                        "arId": None,
                        "transactionAmount": _to_float(repayment.get("transactionAmount"), 0.0),
                    }
                ]

            for child in child_transactions:
                ar_id = str(child.get("arId") or "").strip()
                invoice_pk = None
                if ar_id:
                    invoice_pk = invoice_pk_by_number.get(ar_id)
                if invoice_pk is None:
                    for repayment_ar_id in repayment_ar_ids:
                        invoice_pk = invoice_pk_by_number.get(repayment_ar_id)
                        if invoice_pk is not None:
                            break
                if invoice_pk is not None:
                    linked_by_invoice_key += 1
                elif repayment_credit_plan_id:
                    invoice_pk = invoice_pk_by_credit_plan.get(repayment_credit_plan_id)
                    if invoice_pk is not None:
                        linked_by_credit_plan += 1
                if invoice_pk is None and parent_customer_id is not None:
                    customer_invoice_ids = invoices_by_customer.get(parent_customer_id, [])
                    if len(customer_invoice_ids) == 1:
                        invoice_pk = customer_invoice_ids[0]
                        linked_by_customer_fallback += 1
                amount_paid = _to_float(
                    child.get("transactionAmount") or child.get("principalAmount"), 0.0
                )
                if amount_paid <= 0:
                    continue

                expected_date = None
                is_partial = False
                customer_id = parent_customer_id

                if invoice_pk is not None:
                    inv_row = db.execute(
                        text(
                            """
                            SELECT customer_id, due_date, amount
                            FROM invoices
                            WHERE id = :invoice_id
                            """
                        ),
                        {"invoice_id": invoice_pk},
                    ).one()
                    customer_id = int(inv_row.customer_id)
                    expected_date = inv_row.due_date
                    is_partial = amount_paid < float(inv_row.amount)
                else:
                    unresolved_links += 1

                delay_days = 0
                if expected_date is not None:
                    delay_days = max((payment_date - expected_date).days, 0)

                # Keep load idempotent for the same transaction reference/day/amount.
                db.execute(
                    text(
                        """
                        DELETE FROM payment_transactions
                        WHERE transaction_ref = :transaction_ref
                          AND payment_date = :payment_date
                          AND amount_paid = :amount_paid
                        """
                    ),
                    {
                        "transaction_ref": txn_ref,
                        "payment_date": payment_date,
                        "amount_paid": amount_paid,
                    },
                )

                db.execute(
                    text(
                        """
                        INSERT INTO payment_transactions (
                            invoice_id, customer_id, amount_paid, payment_date, expected_date,
                            delay_days, is_partial, is_after_followup, transaction_ref,
                            payment_mode, transaction_status
                        ) VALUES (
                            :invoice_id, :customer_id, :amount_paid, :payment_date, :expected_date,
                            :delay_days, :is_partial, :is_after_followup, :transaction_ref,
                            :payment_mode, :transaction_status
                        )
                        """
                    ),
                    {
                        "invoice_id": invoice_pk,
                        "customer_id": customer_id,
                        "amount_paid": amount_paid,
                        "payment_date": payment_date,
                        "expected_date": expected_date,
                        "delay_days": delay_days,
                        "is_partial": is_partial,
                        "is_after_followup": False,
                        "transaction_ref": txn_ref,
                        "payment_mode": payment_mode,
                        "transaction_status": status,
                    },
                )
                inserted_transactions += 1

        # Sync FK consistency and derived fields after transaction load.
        db.execute(
            text(
                """
                UPDATE payment_transactions pt
                SET
                    customer_id = i.customer_id,
                    expected_date = COALESCE(pt.expected_date, i.due_date),
                    delay_days = GREATEST(
                        (pt.payment_date - COALESCE(pt.expected_date, i.due_date)),
                        0
                    ),
                    is_partial = CASE
                        WHEN pt.amount_paid < i.amount THEN TRUE
                        ELSE FALSE
                    END
                FROM invoices i
                WHERE pt.invoice_id = i.id
                """
            )
        )

        db.execute(
            text(
                """
                WITH paid AS (
                    SELECT
                        invoice_id,
                        SUM(amount_paid) AS paid_amount
                    FROM payment_transactions
                    WHERE transaction_status = 'success'
                      AND invoice_id IS NOT NULL
                    GROUP BY invoice_id
                )
                UPDATE invoices i
                SET
                    outstanding_amount = GREATEST(i.amount - COALESCE(p.paid_amount, 0), 0),
                    status = CASE
                        WHEN GREATEST(i.amount - COALESCE(p.paid_amount, 0), 0) = 0 THEN 'paid'
                        WHEN NOW()::DATE > i.due_date THEN 'overdue'
                        ELSE 'open'
                    END,
                    days_overdue = CASE
                        WHEN GREATEST(i.amount - COALESCE(p.paid_amount, 0), 0) = 0 THEN 0
                        ELSE GREATEST((NOW()::DATE - i.due_date), 0)
                    END,
                    updated_at = NOW()
                FROM paid p
                WHERE i.id = p.invoice_id
                """
            )
        )

        # Recompute customer rollups from inserted invoices.
        db.execute(
            text(
                """
                UPDATE customers c
                SET
                    total_invoiced = COALESCE(v.total_invoiced, 0),
                    total_overdue = COALESCE(v.total_overdue, 0),
                    num_invoices = COALESCE(v.num_invoices, 0),
                    updated_at = NOW()
                FROM (
                    SELECT
                        customer_id,
                        SUM(amount) AS total_invoiced,
                        SUM(CASE WHEN status = 'overdue' THEN outstanding_amount ELSE 0 END) AS total_overdue,
                        COUNT(*) AS num_invoices
                    FROM invoices
                    GROUP BY customer_id
                ) v
                WHERE c.id = v.customer_id
                """
            )
        )

        db.commit()

    print(f"Loaded customers: {len(customers)}")
    print(f"Loaded invoices: {len(invoice_rows)}")
    print(f"Inserted payment transactions: {inserted_transactions}")
    print(
        "Repayment linking stats:"
        f" by_invoice_key={linked_by_invoice_key},"
        f" by_credit_plan={linked_by_credit_plan},"
        f" by_customer_fallback={linked_by_customer_fallback},"
        f" unresolved={unresolved_links}"
    )
    print("Real data load complete.")


if __name__ == "__main__":
    main()
