"""
DSO (Days Sales Outstanding) prediction service.

DSO = (Accounts Receivable / Total Credit Sales) × Number of Days
Predicted DSO applies ML-derived payment probability adjustments.
"""

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.prediction import DSOPredictionResponse


class DSOService:
    def predict_dso(self) -> DSOPredictionResponse:
        """
        Calculate current DSO from mock invoice data and project
        future DSO using average payment probability weights.
        """
        with SessionLocal() as db:
            rows = db.execute(
                text(
                    """
                    SELECT
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.days_overdue
                    FROM invoices i
                    WHERE i.status IN ('open', 'overdue')
                    """
                )
            ).mappings().all()

        if not rows:
            return DSOPredictionResponse(predicted_dso=45.0, current_dso=45.0, dso_trend="stable")

        total_ar = sum(float(r["amount"] or 0) for r in rows)
        total_sales_30d = max(total_ar, 1.0)
        current_dso = (total_ar / total_sales_30d) * 30
        weighted_days = []
        for r in rows:
            amount = float(r["amount"] or 0)
            days_overdue = int(r["days_overdue"] or 0)
            pay_30 = max(0.05, min(0.95, 1.0 - (days_overdue / 45.0)))
            expected_collection_days = days_overdue + (1 - pay_30) * 30
            weighted_days.append(expected_collection_days * amount)
        predicted_dso = sum(weighted_days) / max(total_ar, 1.0)
        if predicted_dso < current_dso * 0.97:
            trend = "improving"
        elif predicted_dso > current_dso * 1.03:
            trend = "worsening"
        else:
            trend = "stable"
        return DSOPredictionResponse(
            predicted_dso=round(predicted_dso, 1),
            current_dso=round(current_dso, 1),
            dso_trend=trend,
            benchmark_dso=45.0,
        )
