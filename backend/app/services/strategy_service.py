"""
Collection Strategy Optimization Service.

Flow:
  1. generate_candidates()  — produce 3 alternative collection actions
  2. select_best_candidate() — agentic selector scores and picks the optimal action
  3. optimize()             — wraps both steps into the final StrategyResponse
"""

import logging

from app.schemas.strategy import CandidateAction, StrategyRequest, StrategyResponse

logger = logging.getLogger(__name__)

# ── Candidate template library ────────────────────────────────────────────────

_CANDIDATES: dict[str, list[dict]] = {
    "Critical": [
        {
            "action_label": "Call + NACH Mandate",
            "channel": "Call",
            "rationale": "Immediate phone collection with NACH mandate activation — highest real-time recovery rate for critical accounts.",
            "timeline_hours": 2,
            "cost": "High",
            "recovery_estimate": 0.65,
        },
        {
            "action_label": "Anchor / Lender Escalation",
            "channel": "Anchor Escalation",
            "rationale": "Formal escalation through anchor or lender network signals maximum seriousness and triggers priority resolution.",
            "timeline_hours": 4,
            "cost": "Medium",
            "recovery_estimate": 0.55,
        },
        {
            "action_label": "Field Collection Visit",
            "channel": "Field Visit",
            "rationale": "In-person visit for high-value accounts where remote collection has repeatedly failed.",
            "timeline_hours": 24,
            "cost": "Very High",
            "recovery_estimate": 0.50,
        },
    ],
    "High": [
        {
            "action_label": "Collection Call + Email",
            "channel": "Call",
            "rationale": "Dual-channel outreach maximizes response rate for reminder-driven payers.",
            "timeline_hours": 8,
            "cost": "Medium",
            "recovery_estimate": 0.60,
        },
        {
            "action_label": "Formal Demand Letter",
            "channel": "Legal",
            "rationale": "Written legal demand creates paper trail and communicates seriousness without full escalation.",
            "timeline_hours": 24,
            "cost": "Low",
            "recovery_estimate": 0.52,
        },
        {
            "action_label": "Payment Plan Negotiation",
            "channel": "Call",
            "rationale": "Structured installment offer may recover more than forcing full payment on stressed accounts.",
            "timeline_hours": 48,
            "cost": "Low",
            "recovery_estimate": 0.70,
        },
    ],
    "Medium": [
        {
            "action_label": "Follow-up Email + Call",
            "channel": "Call",
            "rationale": "Gentle reminder with follow-up call; appropriate for occasional delayed payers.",
            "timeline_hours": 48,
            "cost": "Low",
            "recovery_estimate": 0.75,
        },
        {
            "action_label": "Automated Payment Reminder Sequence",
            "channel": "Email",
            "rationale": "Automated escalating email sequence; scalable and zero manual effort.",
            "timeline_hours": 24,
            "cost": "Minimal",
            "recovery_estimate": 0.65,
        },
        {
            "action_label": "WhatsApp + Email Nudge",
            "channel": "Email",
            "rationale": "Multi-channel automated nudge; higher open rate and faster acknowledgement.",
            "timeline_hours": 12,
            "cost": "Minimal",
            "recovery_estimate": 0.68,
        },
    ],
    "Low": [
        {
            "action_label": "Standard Payment Reminder",
            "channel": "Email",
            "rationale": "Routine reminder for low-risk accounts approaching or at due date.",
            "timeline_hours": 72,
            "cost": "Minimal",
            "recovery_estimate": 0.90,
        },
        {
            "action_label": "Automated Reminder",
            "channel": "Email",
            "rationale": "Set-and-forget automated nudge — no manual effort required.",
            "timeline_hours": 48,
            "cost": "Minimal",
            "recovery_estimate": 0.88,
        },
        {
            "action_label": "No Action Required",
            "channel": "None",
            "rationale": "Strong payment history; payment expected on time without intervention.",
            "timeline_hours": 168,
            "cost": "Zero",
            "recovery_estimate": 0.95,
        },
    ],
}

_COST_WEIGHTS = {"Zero": 1.0, "Minimal": 0.98, "Low": 0.88, "Medium": 0.72, "High": 0.52, "Very High": 0.35}
_URGENCY_MULTIPLIER = {"Critical": 1.0, "High": 0.85, "Medium": 0.65, "Low": 0.45}


class StrategyService:

    def generate_candidates(self, urgency: str) -> list[CandidateAction]:
        """Return 3 alternative collection actions for the given urgency level."""
        templates = _CANDIDATES.get(urgency, _CANDIDATES["Medium"])
        return [CandidateAction(**t) for t in templates]

    def select_best_candidate(
        self,
        candidates: list[CandidateAction],
        urgency: str,
        delay_probability: float,
        behavior_type: str | None,
        nach_applicable: bool,
        invoice_amount: float,
    ) -> tuple[CandidateAction, str]:
        """
        Agentic Final Selector — scores each candidate and picks the optimal one.

        Scoring formula:
          score = recovery_estimate × cost_weight × urgency_multiplier
                + nach_bonus (if NACH applicable and action includes NACH)
                + amount_bonus (if high value invoice)
        """
        um = _URGENCY_MULTIPLIER.get(urgency, 0.65)
        best_score = -1.0
        best_idx = 0

        for i, c in enumerate(candidates):
            cw = _COST_WEIGHTS.get(c.cost, 0.7)
            score = c.recovery_estimate * cw * um

            # NACH bonus: prefer NACH mandate actions for NACH-eligible borrowers
            if nach_applicable and "NACH" in c.action_label:
                score += 0.15

            # Amount bonus: for high-value invoices, prefer aggressive/fast actions
            if invoice_amount > 2_000_000 and c.timeline_hours <= 8:
                score += 0.08

            # Behavior adjustment: for chronic payers, prefer direct-contact actions
            if behavior_type and "Chronic" in behavior_type and c.channel == "Call":
                score += 0.10

            # Payment plan preference for high delay probability, to ensure partial recovery
            if delay_probability > 0.75 and "Payment Plan" in c.action_label:
                score += 0.07

            c.selection_score = round(min(1.0, score), 3)

            if score > best_score:
                best_score = score
                best_idx = i

        candidates[best_idx].is_selected = True

        winner = candidates[best_idx]
        rationale = (
            f"Selected '{winner.action_label}' with selection score {winner.selection_score:.2f}. "
            f"Recovery estimate: {winner.recovery_estimate:.0%}. "
            f"Cost tier: {winner.cost}. "
            f"SLA: {winner.timeline_hours}h. "
        )
        if nach_applicable and "NACH" in winner.action_label:
            rationale += "NACH mandate applicable — auto-debit reduces collection friction. "
        if delay_probability > 0.75:
            rationale += f"High delay probability ({delay_probability:.0%}) justifies {winner.channel.lower()} channel. "

        return winner, rationale

    def optimize(self, request: StrategyRequest) -> StrategyResponse:
        """
        Full strategy optimization:
          1. Score priority
          2. Determine urgency
          3. Generate candidate actions
          4. Run agentic selector
          5. Return enriched StrategyResponse
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

        # Urgency (driven by combined score signal, not DPD-only override)
        if request.urgency_override:
            urgency = request.urgency_override
        elif priority_score >= 80 or (request.risk_tier == "High" and request.delay_probability >= 0.8):
            urgency = "Critical"
        elif priority_score >= 55 or request.risk_tier == "High":
            urgency = "High"
        elif priority_score >= 30 or request.risk_tier == "Medium":
            urgency = "Medium"
        else:
            urgency = "Low"

        # Candidate Action Generator
        candidates = self.generate_candidates(urgency)

        # Agentic Final Selector
        winner, selection_rationale = self.select_best_candidate(
            candidates=candidates,
            urgency=urgency,
            delay_probability=request.delay_probability,
            behavior_type=request.behavior_type,
            nach_applicable=request.nach_applicable,
            invoice_amount=request.invoice_amount,
        )

        # Field visit override for very high-value, no-NACH critical cases
        if urgency == "Critical" and request.invoice_amount > 3_000_000 and not request.nach_applicable:
            winner.action_label = "Field Collection Visit"
            winner.channel = "Field Visit"
            winner.timeline_hours = 4

        automation_flag = request.automation_feasible and urgency in ("Low", "Medium")

        # Reasoning string
        reason_parts = [
            f"delay probability {request.delay_probability:.0%}",
            f"{request.risk_tier.lower()} risk tier",
        ]
        if request.days_overdue > 0:
            reason_parts.append(f"{request.days_overdue} DPD")
        if request.behavior_type and "Consistent" not in request.behavior_type:
            reason_parts.append(f"{request.behavior_type.lower()} behavior")
        if request.invoice_amount > 500_000:
            reason_parts.append(f"high-value invoice (₹{request.invoice_amount:,.0f})")

        reason = f"Priority {urgency}: " + " + ".join(reason_parts[:4]) + "."

        return StrategyResponse(
            invoice_id=request.invoice_id,
            priority_score=priority_score,
            recommended_action=winner.action_label,
            urgency=urgency,
            channel=winner.channel,
            reason=reason,
            automation_flag=automation_flag,
            next_action_in_hours=winner.timeline_hours,
            candidate_actions=candidates,
            selection_rationale=selection_rationale,
        )

    def rank_portfolio(self, strategies: list[StrategyResponse]) -> list[StrategyResponse]:
        """Assign portfolio rank (1 = most urgent)."""
        sorted_strats = sorted(strategies, key=lambda s: s.priority_score, reverse=True)
        for rank, strat in enumerate(sorted_strats, start=1):
            strat.priority_rank = rank
        return sorted_strats
