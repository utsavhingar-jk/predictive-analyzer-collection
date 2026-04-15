"""
Borrower-Level Prediction Service.

Aggregates all open invoices for a borrower and computes:
  - Weighted delay probability (amount-weighted across invoices)
  - Borrower risk score and tier
  - Expected recovery amount and rate
  - Amount at risk (delay_prob > 0.60)
  - Borrower DSO vs portfolio average
  - Escalation and NACH recommendation
  - Relationship-level action recommendation
"""

import logging
from typing import Optional

from app.schemas.borrower import (
    BorrowerInvoiceSummary,
    BorrowerPortfolioItem,
    BorrowerPredictionRequest,
    BorrowerPredictionResponse,
)
from app.utils.mock_data import (
    MOCK_BEHAVIOR_PROFILES,
    MOCK_INVOICES,
    get_behavior_by_customer_id,
)

logger = logging.getLogger(__name__)

# Portfolio-level benchmark DSO (days)
PORTFOLIO_BENCHMARK_DSO = 45.0
# Shortfall threshold for recovery confidence
HIGH_RECOVERY_THRESHOLD = 0.70
MEDIUM_RECOVERY_THRESHOLD = 0.40


class BorrowerService:

    def predict_borrower(
        self, request: BorrowerPredictionRequest, portfolio_total: float = 0.0
    ) -> BorrowerPredictionResponse:
        """
        Compute full borrower-level risk prediction.

        If invoices are not passed in the request, they are looked up
        from MOCK_INVOICES (replaced with DB query in production).
        """
        invoices = request.invoices

        # Auto-populate from mock data if not supplied
        if not invoices:
            invoices = self._load_borrower_invoices(request.customer_id)

        if not invoices:
            return self._empty_borrower_response(request)

        # ── Aggregate exposure ────────────────────────────────────────────────
        total_outstanding = sum(inv.amount for inv in invoices)
        total_overdue = sum(inv.amount for inv in invoices if inv.status == "overdue")
        open_count = len(invoices)
        overdue_count = sum(1 for inv in invoices if inv.status == "overdue")

        # ── Weighted delay probability (weight = invoice amount) ──────────────
        if total_outstanding > 0:
            weighted_delay_prob = sum(
                inv.delay_probability * inv.amount for inv in invoices
            ) / total_outstanding
        else:
            weighted_delay_prob = 0.0
        weighted_delay_prob = round(weighted_delay_prob, 4)

        # ── Expected recovery ─────────────────────────────────────────────────
        expected_recovery = sum(inv.amount * inv.pay_30_days for inv in invoices)
        recovery_rate = (expected_recovery / total_outstanding) if total_outstanding > 0 else 0.0
        at_risk_amount = sum(
            inv.amount for inv in invoices if inv.delay_probability > 0.60
        )

        recovery_confidence = (
            "High" if recovery_rate >= HIGH_RECOVERY_THRESHOLD
            else "Medium" if recovery_rate >= MEDIUM_RECOVERY_THRESHOLD
            else "Low"
        )

        # ── Borrower risk score (0–100) ───────────────────────────────────────
        # Factors:
        #   delay_prob weight   40%
        #   overdue ratio       20%
        #   credit score        20%
        #   num late payments   10%
        #   concentration       10%
        overdue_ratio = total_overdue / total_outstanding if total_outstanding > 0 else 0.0
        credit_factor = max(0.0, (700 - request.credit_score) / 400)
        late_factor = min(1.0, request.num_late_payments / 10)
        concentration_pct = (total_outstanding / portfolio_total) if portfolio_total > 0 else 0.0
        concentration_factor = min(1.0, concentration_pct / 0.5)  # cap at 50% of portfolio

        raw_score = (
            weighted_delay_prob * 0.40
            + overdue_ratio * 0.20
            + credit_factor * 0.20
            + late_factor * 0.10
            + concentration_factor * 0.10
        )
        borrower_risk_score = int(min(100, round(raw_score * 100)))

        # ── Risk tier ─────────────────────────────────────────────────────────
        if borrower_risk_score >= 65:
            borrower_risk_tier = "High"
        elif borrower_risk_score >= 35:
            borrower_risk_tier = "Medium"
        else:
            borrower_risk_tier = "Low"

        # ── DSO comparison ────────────────────────────────────────────────────
        borrower_dso = request.avg_days_to_pay
        if borrower_dso < PORTFOLIO_BENCHMARK_DSO * 0.85:
            dso_vs_portfolio = "Better"
        elif borrower_dso > PORTFOLIO_BENCHMARK_DSO * 1.15:
            dso_vs_portfolio = "Worse"
        else:
            dso_vs_portfolio = "On Par"

        # ── Behavior profile enrichment ────────────────────────────────────────
        behavior = get_behavior_by_customer_id(str(request.customer_id))
        nach_recommended = behavior.get("nach_recommended", False) if behavior else (
            borrower_risk_tier == "High" and request.num_late_payments >= 3
        )

        # ── Escalation logic ──────────────────────────────────────────────────
        escalation_recommended = (
            borrower_risk_tier == "High"
            and total_outstanding > 50_000
        ) or (
            weighted_delay_prob > 0.75
        ) or (
            overdue_count >= 2 and total_overdue > 30_000
        )

        # ── Relationship action ───────────────────────────────────────────────
        relationship_action = self._relationship_action(
            borrower_risk_tier, total_outstanding, overdue_count,
            weighted_delay_prob, nach_recommended
        )

        # ── Concentration ─────────────────────────────────────────────────────
        concentration_pct = round(concentration_pct * 100, 1)

        # ── Summary ───────────────────────────────────────────────────────────
        summary = self._build_summary(
            request, borrower_risk_tier, borrower_risk_score,
            weighted_delay_prob, expected_recovery, recovery_rate,
            total_outstanding, overdue_count, escalation_recommended,
        )

        return BorrowerPredictionResponse(
            customer_id=str(request.customer_id),
            customer_name=request.customer_name,
            industry=request.industry,
            total_outstanding=round(total_outstanding, 2),
            total_overdue=round(total_overdue, 2),
            open_invoice_count=open_count,
            overdue_invoice_count=overdue_count,
            concentration_pct=concentration_pct,
            weighted_delay_probability=weighted_delay_prob,
            borrower_risk_score=borrower_risk_score,
            borrower_risk_tier=borrower_risk_tier,
            expected_recovery_amount=round(expected_recovery, 2),
            expected_recovery_rate=round(recovery_rate, 4),
            at_risk_amount=round(at_risk_amount, 2),
            recovery_confidence=recovery_confidence,
            borrower_dso=borrower_dso,
            dso_vs_portfolio=dso_vs_portfolio,
            escalation_recommended=escalation_recommended,
            nach_recommended=nach_recommended,
            relationship_action=relationship_action,
            invoices=invoices,
            borrower_summary=summary,
        )

    def get_portfolio_borrowers(self) -> list[BorrowerPortfolioItem]:
        """
        Build a ranked list of all borrowers in the portfolio.
        Groups MOCK_INVOICES by customer and computes borrower-level metrics.
        """
        # Group invoices by customer
        customer_map: dict[str, dict] = {}
        portfolio_total = sum(
            inv["amount"] for inv in MOCK_INVOICES
            if inv["status"] in ("open", "overdue")
        )

        for inv in MOCK_INVOICES:
            if inv["status"] not in ("open", "overdue"):
                continue

            cid = str(inv["customer_id"])
            if cid not in customer_map:
                customer_map[cid] = {
                    "customer_id": cid,
                    "customer_name": inv["customer_name"],
                    "industry": inv.get("industry", "unknown"),
                    "credit_score": inv.get("credit_score", 650),
                    "avg_days_to_pay": inv.get("avg_days_to_pay", 30),
                    "payment_terms": inv.get("payment_terms", 30),
                    "num_late_payments": inv.get("num_late_payments", 0),
                    "invoices": [],
                }

            delay_prob = round(1.0 - inv.get("pay_30_days", 0.5), 4)
            customer_map[cid]["invoices"].append(
                BorrowerInvoiceSummary(
                    invoice_id=inv["invoice_id"],
                    amount=inv["amount"],
                    days_overdue=inv.get("days_overdue", 0),
                    status=inv["status"],
                    risk_label=inv.get("risk_label", "Medium"),
                    delay_probability=delay_prob,
                    pay_30_days=inv.get("pay_30_days", 0.5),
                    recommended_action=inv.get("recommended_action"),
                )
            )

        results: list[BorrowerPortfolioItem] = []
        for cid, data in customer_map.items():
            req = BorrowerPredictionRequest(
                customer_id=data["customer_id"],
                customer_name=data["customer_name"],
                industry=data["industry"],
                credit_score=data["credit_score"],
                avg_days_to_pay=data["avg_days_to_pay"],
                payment_terms=data["payment_terms"],
                num_late_payments=data["num_late_payments"],
                invoices=data["invoices"],
            )
            pred = self.predict_borrower(req, portfolio_total=portfolio_total)
            results.append(
                BorrowerPortfolioItem(
                    customer_id=pred.customer_id,
                    customer_name=pred.customer_name,
                    industry=pred.industry,
                    total_outstanding=pred.total_outstanding,
                    overdue_invoice_count=pred.overdue_invoice_count,
                    borrower_risk_tier=pred.borrower_risk_tier,
                    borrower_risk_score=pred.borrower_risk_score,
                    weighted_delay_probability=pred.weighted_delay_probability,
                    expected_recovery_rate=pred.expected_recovery_rate,
                    at_risk_amount=pred.at_risk_amount,
                    escalation_recommended=pred.escalation_recommended,
                    relationship_action=pred.relationship_action,
                    concentration_pct=pred.concentration_pct,
                )
            )

        # Sort by borrower_risk_score descending
        return sorted(results, key=lambda b: b.borrower_risk_score, reverse=True)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_borrower_invoices(self, customer_id: str) -> list[BorrowerInvoiceSummary]:
        """Look up open invoices for a customer from MOCK_INVOICES."""
        result = []
        for inv in MOCK_INVOICES:
            if str(inv["customer_id"]) != str(customer_id):
                continue
            if inv["status"] not in ("open", "overdue"):
                continue
            delay_prob = round(1.0 - inv.get("pay_30_days", 0.5), 4)
            result.append(
                BorrowerInvoiceSummary(
                    invoice_id=inv["invoice_id"],
                    amount=inv["amount"],
                    days_overdue=inv.get("days_overdue", 0),
                    status=inv["status"],
                    risk_label=inv.get("risk_label", "Medium"),
                    delay_probability=delay_prob,
                    pay_30_days=inv.get("pay_30_days", 0.5),
                    recommended_action=inv.get("recommended_action"),
                )
            )
        return result

    def _relationship_action(
        self,
        risk_tier: str,
        total_outstanding: float,
        overdue_count: int,
        delay_prob: float,
        nach: bool,
    ) -> str:
        if risk_tier == "High" and total_outstanding > 100_000:
            return "Escalate Relationship — Legal Review"
        if risk_tier == "High" and delay_prob > 0.75:
            return "Suspend Credit Facility + Demand Letter"
        if risk_tier == "High" and nach:
            return "Activate NACH Mandate + Collection Call"
        if risk_tier == "High":
            return "Place on Credit Hold + Escalate"
        if risk_tier == "Medium" and overdue_count >= 2:
            return "Collection Call + Payment Plan"
        if risk_tier == "Medium":
            return "Follow-up Email + Call"
        return "Standard Reminder Cycle"

    def _build_summary(
        self,
        req: BorrowerPredictionRequest,
        risk_tier: str,
        risk_score: int,
        delay_prob: float,
        recovery: float,
        recovery_rate: float,
        total: float,
        overdue_count: int,
        escalate: bool,
    ) -> str:
        return (
            f"{req.customer_name} carries a total AR exposure of "
            f"${total:,.0f} across {len(req.invoices)} open invoices "
            f"({overdue_count} overdue). "
            f"Borrower risk score is {risk_score}/100 ({risk_tier} tier) with a "
            f"weighted delay probability of {delay_prob:.0%}. "
            f"Expected 30-day recovery is ${recovery:,.0f} "
            f"({recovery_rate:.0%} of outstanding). "
            f"{'Escalation is recommended. ' if escalate else ''}"
            f"Industry: {req.industry}."
        )

    def _empty_borrower_response(
        self, req: BorrowerPredictionRequest
    ) -> BorrowerPredictionResponse:
        return BorrowerPredictionResponse(
            customer_id=str(req.customer_id),
            customer_name=req.customer_name,
            industry=req.industry,
            total_outstanding=0.0,
            total_overdue=0.0,
            open_invoice_count=0,
            overdue_invoice_count=0,
            concentration_pct=0.0,
            weighted_delay_probability=0.0,
            borrower_risk_score=0,
            borrower_risk_tier="Low",
            expected_recovery_amount=0.0,
            expected_recovery_rate=0.0,
            at_risk_amount=0.0,
            recovery_confidence="High",
            borrower_dso=req.avg_days_to_pay,
            dso_vs_portfolio="On Par",
            escalation_recommended=False,
            nach_recommended=False,
            relationship_action="No Open Invoices",
            invoices=[],
            borrower_summary=f"{req.customer_name} has no open invoices.",
        )
