"""Sentinel External Signals Engine (DB-backed heuristic signals)."""

import logging
from datetime import date

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.sentinel import SentinelCheckResponse, SentinelSignal, WatchlistResponse

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()


class SentinelService:
    def check_customer(self, customer_id: str) -> SentinelCheckResponse:
        """Return sentinel signals for a specific customer from DB-derived heuristics."""
        customer_id = str(customer_id)
        with SessionLocal() as db:
            customer = db.execute(
                text(
                    """
                    SELECT
                        CAST(c.id AS TEXT) AS customer_id,
                        c.name AS customer_name,
                        COALESCE(c.industry, 'unknown') AS industry,
                        COALESCE(c.num_late_payments, 0) AS num_late_payments
                    FROM customers c
                    WHERE CAST(c.id AS TEXT) = :customer_id
                    LIMIT 1
                    """
                ),
                {"customer_id": customer_id},
            ).mappings().one_or_none()

            invoice_rows = db.execute(
                text(
                    """
                    SELECT
                        i.invoice_number,
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.days_overdue,
                        i.status
                    FROM invoices i
                    WHERE CAST(i.customer_id AS TEXT) = :customer_id
                      AND i.status IN ('open', 'overdue')
                    ORDER BY i.days_overdue DESC, i.due_date ASC
                    """
                ),
                {"customer_id": customer_id},
            ).mappings().all()

        if not customer:
            return SentinelCheckResponse(
                customer_id=customer_id,
                customer_name=f"Customer {customer_id}",
                industry="unknown",
                is_flagged=False,
                risk_level="Clear",
                signals=[],
                overall_sentinel_score=0,
                recommendation="Customer not found in portfolio.",
                last_checked=TODAY,
                high_signal_count=0,
                medium_signal_count=0,
                primary_invoice_id=None,
            )

        signals: list[SentinelSignal] = []
        total_outstanding = sum(float(r["amount"] or 0) for r in invoice_rows)
        overdue_count = sum(1 for r in invoice_rows if int(r["days_overdue"] or 0) > 0)
        max_days_overdue = max((int(r["days_overdue"] or 0) for r in invoice_rows), default=0)
        num_late_payments = int(customer["num_late_payments"] or 0)
        primary_invoice_id = str(invoice_rows[0]["invoice_number"]) if invoice_rows else None

        if max_days_overdue >= 45:
            signals.append(
                SentinelSignal(
                    signal_type="ap_contact_failure",
                    severity="High",
                    description=f"Oldest receivable is {max_days_overdue} days overdue; collection contact risk elevated.",
                    source="Sentinel Rules",
                    detected_at=TODAY,
                )
            )
        if overdue_count >= 2:
            signals.append(
                SentinelSignal(
                    signal_type="email_anomaly",
                    severity="Medium",
                    description=f"{overdue_count} active overdue invoices indicate communication/payment slippage.",
                    source="Sentinel Rules",
                    detected_at=TODAY,
                )
            )
        if num_late_payments >= 3:
            signals.append(
                SentinelSignal(
                    signal_type="leadership_change",
                    severity="Medium",
                    description="Repeated delayed payment pattern suggests approval/workflow instability.",
                    source="Sentinel Rules",
                    detected_at=TODAY,
                )
            )
        if total_outstanding >= 5000:
            signals.append(
                SentinelSignal(
                    signal_type="sector_news",
                    severity="Medium",
                    description="High outstanding concentration triggers sector-stress precautionary signal.",
                    source="Sentinel Rules",
                    detected_at=TODAY,
                )
            )
        if max_days_overdue >= 30:
            signals.append(
                SentinelSignal(
                    signal_type="news_alert",
                    severity="High",
                    description="Prolonged overdue period indicates elevated external-default likelihood.",
                    source="Sentinel Rules",
                    detected_at=TODAY,
                )
            )

        high_count = sum(1 for s in signals if s.severity == "High")
        medium_count = sum(1 for s in signals if s.severity == "Medium")
        score = min(100, high_count * 35 + medium_count * 18 + min(max_days_overdue // 2, 20))

        if score >= 80:
            risk_level = "Critical"
            recommendation = "Immediate escalation and senior collector intervention."
        elif score >= 55:
            risk_level = "High"
            recommendation = "Prioritize proactive outreach and monitor daily."
        elif score >= 30:
            risk_level = "Medium"
            recommendation = "Continue tight follow-up and monitor external risk drift."
        else:
            risk_level = "Clear"
            recommendation = "No material external risk signal; continue standard cadence."

        return SentinelCheckResponse(
            customer_id=str(customer["customer_id"]),
            customer_name=str(customer["customer_name"]),
            industry=str(customer["industry"]),
            is_flagged=risk_level != "Clear",
            risk_level=risk_level,
            signals=signals,
            overall_sentinel_score=score,
            recommendation=recommendation,
            last_checked=TODAY,
            high_signal_count=high_count,
            medium_signal_count=medium_count,
            primary_invoice_id=primary_invoice_id,
        )

    def get_watchlist(self) -> WatchlistResponse:
        """Return all flagged customers sorted by sentinel score."""
        with SessionLocal() as db:
            customer_ids = [
                str(r.customer_id)
                for r in db.execute(
                    text(
                        """
                        SELECT DISTINCT CAST(customer_id AS TEXT) AS customer_id
                        FROM invoices
                        WHERE status IN ('open', 'overdue')
                        ORDER BY customer_id
                        """
                    )
                ).fetchall()
            ]

        flagged: list[SentinelCheckResponse] = []
        for customer_id in customer_ids:
            resp = self.check_customer(customer_id)
            if resp.is_flagged:
                flagged.append(resp)

        flagged.sort(key=lambda x: x.overall_sentinel_score, reverse=True)
        critical = sum(1 for c in flagged if c.risk_level == "Critical")
        high = sum(1 for c in flagged if c.risk_level == "High")

        return WatchlistResponse(
            total_flagged=len(flagged),
            critical_count=critical,
            high_count=high,
            customers=flagged,
        )
