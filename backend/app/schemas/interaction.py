"""Pydantic schemas for Collections Interaction History and Action Effectiveness."""

from typing import Optional
from pydantic import BaseModel, Field


class CollectionInteraction(BaseModel):
    """One recorded touchpoint in the collections lifecycle."""

    interaction_id: str
    invoice_id: str
    customer_id: str
    customer_name: str
    action_type: str   # "Call" | "Email" | "Legal Notice" | "Field Visit" | "NACH Trigger" | "Payment Plan"
    channel: str       # "phone" | "email" | "in_person" | "whatsapp" | "legal"
    outcome: str       # "collected_full" | "collected_partial" | "ptp_given" | "broken_ptp"
                       # | "no_answer" | "refused" | "dispute_raised" | "no_response" | "escalated"
    date: str          # ISO date string
    collector_name: Optional[str] = None
    amount_recovered: Optional[float] = None   # INR, if any payment received
    ptp_amount: Optional[float] = None         # Promise-to-Pay amount if given
    ptp_date: Optional[str] = None             # Promised date
    broken_ptp: bool = False
    notes: Optional[str] = None
    days_to_resolution: Optional[int] = None   # If collected, how many days it took


class ActionEffectiveness(BaseModel):
    """Analytics on how well a given action type works for this customer."""

    action_type: str
    total_attempts: int
    success_count: int
    success_rate: float = Field(..., ge=0, le=1)  # fraction resulting in payment/PTP
    avg_days_to_collect: Optional[float] = None
    recommended: bool = False


class InteractionHistoryResponse(BaseModel):
    """Full interaction history + effectiveness analytics for an invoice/customer."""

    invoice_id: str
    customer_id: str
    customer_name: str
    interactions: list[CollectionInteraction]
    action_effectiveness: list[ActionEffectiveness]
    best_action: str                           # AI-derived best action from history
    total_interactions: int
    total_recovered: float = 0.0              # INR recovered so far
    open_ptp_amount: Optional[float] = None   # Active promise-to-pay outstanding
    has_broken_ptp: bool = False
    learning_confidence_boost: float = 0.0    # how much history improved confidence (0-1)
    data_points_used: int = 0                 # number of historical records used
