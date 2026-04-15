"""
Collection Strategy Optimization Service.

Takes delay prediction + invoice signals and returns a prioritised,
channel-specific collection strategy recommendation.
"""

import logging

from app.schemas.strategy import StrategyRequest, StrategyResponse

logger = logging.getLogger(__name__)

# Action matrix: (urgency, channel, action_label, next_action_hours)
_ACTION_MATRIX = {
    ("Critical", True):   ("Call + NACH Mandate",           "Call",              2),
    ("Critical", False):  ("Escalate to Anchor",            "Anchor Escalation", 4),
    ("High",     True):   ("Collection Call + Email",       "Call",              8),
    ("High",     False):  ("Formal Demand Letter",          "Legal",             12),
    ("Medium",   True):   ("Automated Payment Reminder",    "Email",             24),
    ("Medium",   False):  ("Follow-up Email + Call",        "Call",              48),
    ("Low",      True):   ("Automated Reminder",            "Email",             72),
    ("Low",      False):  ("Standard Payment Reminder",     "Email",             72),
}


class StrategyService:
    def optimize(self, request: StrategyRequest) -> StrategyResponse:
        """
        Compute priority score, urgency, and recommended collection action.

        Priority score formula:
          base_score   = delay_probability × 60
          amount_bonus = log-scaled invoice amount contribution (max 20)
          dpd_bonus    = days_overdue contribution (max 10)
          behavior_bonus = chronic/reminder payer bonus (max 10)
        """
        # Priority score (0–100)
        base_score = request.delay_probability * 60
        amount_bonus = min(20.0, (request.invoice_amount / 10_000) * 2)
        dpd_bonus = min(10.0, request.days_overdue / 9)
        behavior_bonus = 0.0
        if request.behavior_type:
            if "Chronic" in request.behavior_type or "High Risk" in request.behavior_type:
                behavior_bonus = 10.0
            elif "Reminder" in request.behavior_type or "Partial" in request.behavior_type:
                behavior_bonus = 5.0

        priority_score = int(min(100, base_score + amount_bonus + dpd_bonus + behavior_bonus))

        # Urgency determination
        if request.urgency_override:
            urgency = request.urgency_override
        elif priority_score >= 80 or request.days_overdue > 60:
            urgency = "Critical"
        elif priority_score >= 55 or request.days_overdue > 30:
            urgency = "High"
        elif priority_score >= 30:
            urgency = "Medium"
        else:
            urgency = "Low"

        # Automation flag — automate if low urgency and automation feasible
        automation_flag = request.automation_feasible and urgency in ("Low", "Medium")

        # Look up action from matrix
        action_label, channel, next_hours = _ACTION_MATRIX.get(
            (urgency, request.nach_applicable),
            _ACTION_MATRIX[(urgency, False)],
        )

        # Override channel for field visit on high-amount, high-urgency
        if urgency == "Critical" and request.invoice_amount > 200_000 and not request.nach_applicable:
            channel = "Field Visit"
            action_label = "Field Collection Visit"
            next_hours = 4

        # Build reasoning string
        reason_parts = [
            f"delay probability {request.delay_probability:.0%}",
            f"{request.risk_tier.lower()} risk tier",
        ]
        if request.days_overdue > 0:
            reason_parts.append(f"{request.days_overdue} DPD")
        if request.behavior_type and "Consistent" not in request.behavior_type:
            reason_parts.append(f"{request.behavior_type.lower()} behavior")
        if request.invoice_amount > 50_000:
            reason_parts.append(f"high-value invoice (${request.invoice_amount:,.0f})")

        reason = f"Priority {urgency}: " + " + ".join(reason_parts[:4]) + "."

        return StrategyResponse(
            invoice_id=request.invoice_id,
            priority_score=priority_score,
            recommended_action=action_label,
            urgency=urgency,
            channel=channel,
            reason=reason,
            automation_flag=automation_flag,
            next_action_in_hours=next_hours,
        )

    def rank_portfolio(self, strategies: list[StrategyResponse]) -> list[StrategyResponse]:
        """Assign portfolio rank (1 = most urgent) to a list of strategies."""
        sorted_strats = sorted(strategies, key=lambda s: s.priority_score, reverse=True)
        for rank, strat in enumerate(sorted_strats, start=1):
            strat.priority_rank = rank
        return sorted_strats
