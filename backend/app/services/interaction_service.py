"""
Collections Interaction History Service.

Provides:
  - Per-invoice interaction history
  - Action effectiveness analytics (which actions work for this borrower)
  - Best-action recommendation derived from historical outcomes
  - Learning confidence boost: how much history improves prediction certainty
"""

import logging
from collections import defaultdict

from app.schemas.interaction import (
    ActionEffectiveness,
    CollectionInteraction,
    InteractionHistoryResponse,
)
from app.utils.mock_interactions import MOCK_INTERACTIONS

logger = logging.getLogger(__name__)

# Outcomes that count as "success" (resulted in payment or firm PTP honoured)
SUCCESS_OUTCOMES = {"collected_full", "collected_partial", "ptp_given"}
POSITIVE_OUTCOMES = {"collected_full", "collected_partial"}


class InteractionService:

    def get_by_invoice(self, invoice_id: str) -> InteractionHistoryResponse:
        """Return full interaction history + effectiveness analytics for one invoice."""
        raw = [i for i in MOCK_INTERACTIONS if i["invoice_id"] == invoice_id]

        if not raw:
            return self._empty_response(invoice_id)

        sample = raw[0]
        interactions = [CollectionInteraction(**r) for r in raw]

        effectiveness = self._compute_effectiveness(raw)
        best_action = self._derive_best_action(effectiveness, raw)
        total_recovered = sum(
            r.get("amount_recovered") or 0.0
            for r in raw
            if r.get("amount_recovered")
        )
        open_ptp = next(
            (r.get("ptp_amount") for r in reversed(raw)
             if r.get("ptp_amount") and not r.get("broken_ptp")
             and r["outcome"] == "ptp_given"),
            None,
        )
        has_broken = any(r.get("broken_ptp") for r in raw)
        confidence_boost = min(0.25, len(raw) * 0.04)  # +4% per data point, cap 25%

        return InteractionHistoryResponse(
            invoice_id=invoice_id,
            customer_id=sample["customer_id"],
            customer_name=sample["customer_name"],
            interactions=interactions,
            action_effectiveness=effectiveness,
            best_action=best_action,
            total_interactions=len(raw),
            total_recovered=total_recovered,
            open_ptp_amount=open_ptp,
            has_broken_ptp=has_broken,
            learning_confidence_boost=round(confidence_boost, 2),
            data_points_used=len(raw),
        )

    def get_portfolio_effectiveness(self) -> dict:
        """
        Portfolio-wide action effectiveness — 'which action works best overall'.
        Returns summary dict keyed by action_type.
        """
        by_action: dict[str, list[str]] = defaultdict(list)
        for r in MOCK_INTERACTIONS:
            by_action[r["action_type"]].append(r["outcome"])

        summary = {}
        for action, outcomes in by_action.items():
            successes = sum(1 for o in outcomes if o in SUCCESS_OUTCOMES)
            payments = sum(1 for o in outcomes if o in POSITIVE_OUTCOMES)
            summary[action] = {
                "total": len(outcomes),
                "success_count": successes,
                "success_rate": round(successes / len(outcomes), 2) if outcomes else 0,
                "payment_rate": round(payments / len(outcomes), 2) if outcomes else 0,
            }

        return summary

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_effectiveness(self, interactions: list[dict]) -> list[ActionEffectiveness]:
        """Compute per-action-type success rate from this invoice's history."""
        by_type: dict[str, list[str]] = defaultdict(list)
        for i in interactions:
            by_type[i["action_type"]].append(i["outcome"])

        results = []
        best_rate = max(
            (sum(1 for o in outs if o in SUCCESS_OUTCOMES) / len(outs) if outs else 0)
            for outs in by_type.values()
        ) if by_type else 0

        for action_type, outcomes in by_type.items():
            total = len(outcomes)
            success = sum(1 for o in outcomes if o in SUCCESS_OUTCOMES)
            rate = round(success / total, 2) if total else 0
            results.append(ActionEffectiveness(
                action_type=action_type,
                total_attempts=total,
                success_count=success,
                success_rate=rate,
                recommended=(rate == best_rate and total >= 1),
            ))

        results.sort(key=lambda x: x.success_rate, reverse=True)
        return results

    def _derive_best_action(
        self, effectiveness: list[ActionEffectiveness], raw: list[dict]
    ) -> str:
        """
        Choose the best next action based on what has worked historically.
        Falls back to escalation if nothing has worked.
        """
        if not effectiveness:
            return "Escalate to Anchor"

        best = effectiveness[0]
        has_broken_ptp = any(r.get("broken_ptp") for r in raw)
        last_outcome = raw[-1]["outcome"] if raw else None

        if has_broken_ptp and best.success_rate < 0.3:
            return "Legal Notice + Anchor Escalation"

        if last_outcome == "escalated":
            return "Lender / Anchor Intervention"

        action_map = {
            "Call": "Collection Call",
            "Email": "Follow-up Email",
            "Legal Notice": "Formal Demand Letter",
            "Field Visit": "Field Collection Visit",
            "NACH Trigger": "NACH Mandate Activation",
            "Payment Plan": "Payment Plan Negotiation",
            "WhatsApp": "WhatsApp + Call Outreach",
        }
        return action_map.get(best.action_type, best.action_type)

    def _empty_response(self, invoice_id: str) -> InteractionHistoryResponse:
        return InteractionHistoryResponse(
            invoice_id=invoice_id,
            customer_id="",
            customer_name="",
            interactions=[],
            action_effectiveness=[],
            best_action="No interaction history available",
            total_interactions=0,
        )
