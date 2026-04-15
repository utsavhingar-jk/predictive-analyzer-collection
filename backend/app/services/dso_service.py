"""
DSO (Days Sales Outstanding) prediction service.

DSO = (Accounts Receivable / Total Credit Sales) × Number of Days
Predicted DSO applies ML-derived payment probability adjustments.
"""

from app.schemas.prediction import DSOPredictionResponse
from app.utils.mock_data import MOCK_INVOICES


class DSOService:
    def predict_dso(self) -> DSOPredictionResponse:
        """
        Calculate current DSO from mock invoice data and project
        future DSO using average payment probability weights.
        """
        if not MOCK_INVOICES:
            return DSOPredictionResponse(
                predicted_dso=45.0,
                current_dso=45.0,
                dso_trend="stable",
            )

        total_ar = sum(inv["amount"] for inv in MOCK_INVOICES if inv["status"] == "open")
        total_sales_30d = sum(inv["amount"] for inv in MOCK_INVOICES)
        days = 30

        current_dso = (total_ar / max(total_sales_30d, 1)) * days

        # Weight predicted DSO by payment probability — higher p30 → lower DSO
        weighted_days = []
        for inv in MOCK_INVOICES:
            p30 = inv.get("pay_30_days", 0.6)
            expected_collection_days = inv.get("days_overdue", 0) + (1 - p30) * 30
            weighted_days.append(expected_collection_days * inv["amount"])

        total_weighted = sum(weighted_days)
        total_amount = sum(inv["amount"] for inv in MOCK_INVOICES)
        predicted_dso = total_weighted / max(total_amount, 1)

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
