"""
Sentinel External Signals Engine.

Monitors external risk signals for borrowers:
  - Leadership / ownership changes
  - News alerts (NCLT, regulatory, sector stress)
  - AP contact / email communication anomalies
  - Sector-level distress signals

Currently uses mocked signal data per customer.
In production: integrate with news APIs, LinkedIn, CRM email monitors.
"""

import logging
from datetime import date

from app.schemas.sentinel import SentinelCheckResponse, SentinelSignal, WatchlistResponse
from app.utils.mock_data import MOCK_INVOICES

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()

# ── Pre-computed mock sentinel signals per customer_id ───────────────────────

MOCK_SENTINEL_DB: dict[str, dict] = {
    "4": {
        "is_flagged": True,
        "risk_level": "Critical",
        "overall_sentinel_score": 92,
        "recommendation": "Immediate escalation. Multiple systemic signals detected. Do not extend credit.",
        "signals": [
            SentinelSignal(
                signal_type="leadership_change",
                severity="High",
                description="CTO resigned last month; payment authorization workflow is disrupted.",
                source="LinkedIn",
                detected_at="2024-03-28",
            ),
            SentinelSignal(
                signal_type="news_alert",
                severity="High",
                description="Company cited in NCLT insolvency proceedings; debt restructuring under review.",
                source="Economic Times",
                detected_at="2024-04-02",
            ),
            SentinelSignal(
                signal_type="email_anomaly",
                severity="Medium",
                description="Accounts payable mailbox bouncing since 7 days; no auto-reply configured.",
                source="Email Monitor",
                detected_at="2024-04-08",
            ),
        ],
    },
    "9": {
        "is_flagged": True,
        "risk_level": "Critical",
        "overall_sentinel_score": 88,
        "recommendation": "Halt credit extension. AP contact unreachable. Initiate field recovery immediately.",
        "signals": [
            SentinelSignal(
                signal_type="ap_contact_failure",
                severity="High",
                description="Designated AP contact unreachable for 14 consecutive days across phone and email.",
                source="CRM",
                detected_at="2024-04-01",
            ),
            SentinelSignal(
                signal_type="news_alert",
                severity="High",
                description="SEBI regulatory inquiry reported in Mint; infrastructure expansion project stalled.",
                source="Mint",
                detected_at="2024-04-05",
            ),
        ],
    },
    "13": {
        "is_flagged": True,
        "risk_level": "High",
        "overall_sentinel_score": 74,
        "recommendation": "Monitor closely. New CFO onboarded — expect payment delays during transition.",
        "signals": [
            SentinelSignal(
                signal_type="leadership_change",
                severity="Medium",
                description="New CFO onboarded 2 weeks ago; payment approval cycle extended to 60+ days.",
                source="LinkedIn",
                detected_at="2024-04-06",
            ),
            SentinelSignal(
                signal_type="email_anomaly",
                severity="Medium",
                description="Average email response time is 3x above baseline; possible backlog.",
                source="Email Monitor",
                detected_at="2024-04-09",
            ),
        ],
    },
    "1": {
        "is_flagged": True,
        "risk_level": "High",
        "overall_sentinel_score": 62,
        "recommendation": "Sector-level stress. Prioritize collection call before month-end.",
        "signals": [
            SentinelSignal(
                signal_type="sector_news",
                severity="Medium",
                description="Auto sector cash crunch reported; component manufacturers facing 45–60 day payment delays.",
                source="Business Standard",
                detected_at="2024-04-10",
            ),
        ],
    },
    "7": {
        "is_flagged": True,
        "risk_level": "High",
        "overall_sentinel_score": 65,
        "recommendation": "Steel sector under pressure. Escalate to anchor if no payment in 7 days.",
        "signals": [
            SentinelSignal(
                signal_type="sector_news",
                severity="Medium",
                description="Steel sector under margin pressure; export orders down 23%. Receivables cycle stretching.",
                source="Business Line",
                detected_at="2024-04-07",
            ),
        ],
    },
    "15": {
        "is_flagged": True,
        "risk_level": "High",
        "overall_sentinel_score": 68,
        "recommendation": "GST dispute affecting cash flow. Offer payment plan to secure partial recovery.",
        "signals": [
            SentinelSignal(
                signal_type="news_alert",
                severity="Medium",
                description="Tax dispute under GST audit; cash locked in escrow impacting payables.",
                source="Tax Monitor",
                detected_at="2024-04-11",
            ),
        ],
    },
}

# Customers with no signals — appear in watchlist as "Clear"
_CLEAR_TEMPLATE = {
    "is_flagged": False,
    "risk_level": "Clear",
    "overall_sentinel_score": 0,
    "recommendation": "No external risk signals detected. Continue standard follow-up.",
    "signals": [],
}


class SentinelService:

    def check_customer(self, customer_id: str) -> SentinelCheckResponse:
        """Return sentinel signals for a specific customer."""
        customer_id = str(customer_id)
        inv = next(
            (i for i in MOCK_INVOICES if str(i["customer_id"]) == customer_id),
            None,
        )
        customer_name = inv["customer_name"] if inv else f"Customer {customer_id}"
        industry = inv.get("industry", "unknown") if inv else "unknown"

        data = MOCK_SENTINEL_DB.get(customer_id, _CLEAR_TEMPLATE)

        signals = data["signals"]
        high_count = sum(1 for s in signals if s.severity == "High")
        medium_count = sum(1 for s in signals if s.severity == "Medium")

        return SentinelCheckResponse(
            customer_id=customer_id,
            customer_name=customer_name,
            industry=industry,
            is_flagged=data["is_flagged"],
            risk_level=data["risk_level"],
            signals=signals,
            overall_sentinel_score=data["overall_sentinel_score"],
            recommendation=data["recommendation"],
            last_checked=TODAY,
            high_signal_count=high_count,
            medium_signal_count=medium_count,
        )

    def get_watchlist(self) -> WatchlistResponse:
        """Return all flagged customers sorted by sentinel score."""
        flagged: list[SentinelCheckResponse] = []

        for customer_id, data in MOCK_SENTINEL_DB.items():
            if data["is_flagged"]:
                flagged.append(self.check_customer(customer_id))

        flagged.sort(key=lambda x: x.overall_sentinel_score, reverse=True)

        critical = sum(1 for c in flagged if c.risk_level == "Critical")
        high = sum(1 for c in flagged if c.risk_level == "High")

        return WatchlistResponse(
            total_flagged=len(flagged),
            critical_count=critical,
            high_count=high,
            customers=flagged,
        )
