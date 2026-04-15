"""
Collection prioritization service.

Priority Score = invoice_amount × delay_probability
Invoices are sorted descending so collectors tackle highest-impact items first.
"""

from app.schemas.prediction import PrioritizedInvoice
from app.utils.mock_data import MOCK_INVOICES


class PrioritizationService:
    def get_prioritized_worklist(self) -> list[PrioritizedInvoice]:
        """
        Build the collector worklist by computing priority scores for all
        open invoices and sorting them from highest to lowest.
        """
        worklist: list[PrioritizedInvoice] = []

        for inv in MOCK_INVOICES:
            if inv["status"] not in ("open", "overdue"):
                continue

            delay_probability = 1.0 - inv.get("pay_30_days", 0.5)
            priority_score = inv["amount"] * delay_probability

            worklist.append(
                PrioritizedInvoice(
                    invoice_id=inv["invoice_id"],
                    customer_name=inv["customer_name"],
                    amount=inv["amount"],
                    days_overdue=inv.get("days_overdue", 0),
                    risk_label=inv.get("risk_label", "Medium"),
                    delay_probability=round(delay_probability, 4),
                    priority_score=round(priority_score, 2),
                    recommended_action=inv.get("recommended_action"),
                )
            )

        return sorted(worklist, key=lambda x: x.priority_score, reverse=True)
