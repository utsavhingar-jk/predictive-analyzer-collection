"""Pydantic schemas for the Sentinel External Signals Engine."""

from typing import Optional
from pydantic import BaseModel, Field


class SentinelSignal(BaseModel):
    """One detected external risk signal for a customer."""

    signal_type: str        # "leadership_change" | "news_alert" | "email_anomaly" | "ap_contact_failure" | "sector_news"
    severity: str           # "High" | "Medium" | "Low"
    description: str
    source: str             # "LinkedIn" | "Economic Times" | "Email Monitor" | "CRM" | etc.
    detected_at: str        # ISO date string


class SentinelCheckResponse(BaseModel):
    """Complete Sentinel result for one customer."""

    customer_id: str
    customer_name: str
    industry: str
    is_flagged: bool
    risk_level: str          # "Critical" | "High" | "Medium" | "Clear"
    signals: list[SentinelSignal]
    overall_sentinel_score: int = Field(..., ge=0, le=100)
    recommendation: str
    last_checked: str        # ISO date string
    high_signal_count: int = 0
    medium_signal_count: int = 0
    primary_invoice_id: Optional[str] = None


class WatchlistResponse(BaseModel):
    """Portfolio-level Sentinel watchlist."""

    total_flagged: int
    critical_count: int
    high_count: int
    customers: list[SentinelCheckResponse]
