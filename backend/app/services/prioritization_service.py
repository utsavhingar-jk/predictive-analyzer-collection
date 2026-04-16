"""
Collection prioritization service.

Priority Score = invoice_amount × delay_probability
Invoices are sorted descending so collectors tackle highest-impact items first.
"""

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.prediction import PrioritizedInvoice
from app.services.risk_scoring import (
    build_amount_reference,
    delay_probability_from_score,
    risk_score,
    risk_tier_from_score,
)


class PrioritizationService:
    def get_prioritized_worklist(self) -> list[PrioritizedInvoice]:
        """
        Build the collector worklist by computing priority scores for all
        open invoices and sorting them from highest to lowest.
        """
        with SessionLocal() as db:
            rows = db.execute(
                text(
                    """
                    SELECT
                        i.invoice_number AS invoice_id,
                        c.name AS customer_name,
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.days_overdue,
                        i.status
                    FROM invoices i
                    LEFT JOIN customers c ON c.id = i.customer_id
                    WHERE i.status IN ('open', 'overdue')
                    """
                )
            ).mappings().all()
        amount_reference = build_amount_reference(float(r["amount"] or 0) for r in rows)
        worklist: list[PrioritizedInvoice] = []
        for row in rows:
            days_overdue = int(row["days_overdue"] or 0)
            amount = float(row["amount"] or 0)
            score = risk_score(days_overdue, amount, amount_reference)
            delay_probability = delay_probability_from_score(score)
            risk_label = risk_tier_from_score(score)
            if risk_label == "High":
                risk_label = "High"
                recommended_action = "Formal demand and collector follow-up"
            elif risk_label == "Medium":
                risk_label = "Medium"
                recommended_action = "Reminder call and payment plan follow-up"
            else:
                risk_label = "Low"
                recommended_action = "Automated reminder"
            priority_score = amount * delay_probability
            worklist.append(
                PrioritizedInvoice(
                    invoice_id=str(row["invoice_id"]),
                    customer_name=str(row["customer_name"] or "Unknown Customer"),
                    amount=round(amount, 2),
                    days_overdue=days_overdue,
                    risk_label=risk_label,
                    delay_probability=round(delay_probability, 4),
                    priority_score=round(priority_score, 2),
                    recommended_action=recommended_action,
                )
            )
        return sorted(worklist, key=lambda x: x.priority_score, reverse=True)
