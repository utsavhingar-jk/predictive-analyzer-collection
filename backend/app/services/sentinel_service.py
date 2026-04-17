"""Sentinel External Signals Engine (DB-backed heuristic signals)."""

import logging
from datetime import date

from app.schemas.sentinel import SentinelCheckResponse, SentinelSignal, WatchlistResponse
from app.services.portfolio_intelligence_service import (
    PortfolioCustomerSnapshot,
    PortfolioIntelligenceService,
)

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()


class SentinelService:
    def __init__(self) -> None:
        self.portfolio_svc = PortfolioIntelligenceService()

    def check_customer(self, customer_id: str) -> SentinelCheckResponse:
        """Return sentinel signals for a specific customer from canonical portfolio facts."""
        customer_id = str(customer_id)
        try:
            snapshot_map = self._load_customer_snapshot_map()
            snapshot = snapshot_map.get(customer_id)
        except Exception as exc:
            logger.warning("SentinelService: portfolio intelligence unavailable (%s)", exc)
            snapshot = None

        if not snapshot:
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

        return self._check_snapshot(snapshot)

    def get_watchlist(self) -> WatchlistResponse:
        """Return all flagged customers sorted by sentinel score."""
        snapshot_map = self._load_customer_snapshot_map()
        flagged: list[SentinelCheckResponse] = []
        for snapshot in snapshot_map.values():
            response = self._check_snapshot(snapshot)
            if response.is_flagged:
                flagged.append(response)
        flagged.sort(key=lambda x: x.overall_sentinel_score, reverse=True)
        critical = sum(1 for c in flagged if c.risk_level == "Critical")
        high = sum(1 for c in flagged if c.risk_level == "High")

        return WatchlistResponse(
            total_flagged=len(flagged),
            critical_count=critical,
            high_count=high,
            customers=flagged,
        )

    def _load_customer_snapshot_map(self) -> dict[str, PortfolioCustomerSnapshot]:
        snapshots = self.portfolio_svc.build_customer_snapshots_sync()
        return {snapshot.customer_id: snapshot for snapshot in snapshots}

    def _check_snapshot(self, snapshot: PortfolioCustomerSnapshot) -> SentinelCheckResponse:
        signals: list[SentinelSignal] = []
        total_outstanding = snapshot.total_outstanding()
        overdue_count = snapshot.overdue_invoice_count()
        max_days_overdue = max(
            (int(item.invoice["days_overdue"]) for item in snapshot.invoices),
            default=0,
        )
        num_late_payments = int(snapshot.num_late_payments or 0)
        weighted_delay_prob = snapshot.weighted_delay_probability()
        primary_invoice_id = snapshot.primary_invoice_id()

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
        if weighted_delay_prob >= 0.65 and max_days_overdue < 30:
            signals.append(
                SentinelSignal(
                    signal_type="news_alert",
                    severity="High" if weighted_delay_prob >= 0.8 else "Medium",
                    description=(
                        f"Canonical portfolio view shows {round(weighted_delay_prob * 100)}% "
                        "weighted delay probability across this borrower."
                    ),
                    source="Portfolio Intelligence",
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
            customer_id=snapshot.customer_id,
            customer_name=snapshot.customer_name,
            industry=snapshot.industry,
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
