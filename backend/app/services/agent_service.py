"""
Orchestrated OpenAI Agent Service.

Runs the full intelligence pipeline for a single invoice case:
  1. Analyze payment behavior
  2. Predict delay (enriched with behavior)
  3. Optimize collection strategy
  4. Generate GPT-4o business summary
  5. Return unified response

Falls back to rule-based summary if OpenAI is unavailable.
"""

import json
import logging

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas.agent import AgentCaseRequest, AgentCaseResponse
from app.schemas.behavior import PaymentBehaviorRequest
from app.schemas.delay import DelayPredictionRequest
from app.schemas.strategy import StrategyRequest
from app.services.behavior_service import BehaviorService
from app.services.delay_service import DelayService
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)
settings = get_settings()

AGENT_SYSTEM_PROMPT = """You are a senior collections intelligence analyst. 
You receive a structured case report and produce a concise, business-readable summary 
for a collections manager.

Write 2-4 sentences covering:
1. Who the borrower is and their payment personality
2. The delay risk and key drivers  
3. The recommended collection action and why
4. Any additional urgency factors

Be direct and professional. Output only the business summary text, no JSON."""


class AgentService:
    def __init__(self) -> None:
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.behavior_svc = BehaviorService()
        self.delay_svc = DelayService()
        self.strategy_svc = StrategyService()

    async def analyze_case(self, req: AgentCaseRequest) -> AgentCaseResponse:
        """
        Full intelligence pipeline for one invoice case.

        Steps execute sequentially so each layer feeds the next.
        """
        # ── Step 1: Payment Behavior ──────────────────────────────────────────
        behavior_req = PaymentBehaviorRequest(
            customer_id=req.customer_id,
            customer_name=req.customer_name,
            historical_on_time_ratio=req.historical_on_time_ratio,
            avg_delay_days=req.avg_delay_days,
            repayment_consistency=req.repayment_consistency,
            partial_payment_frequency=req.partial_payment_frequency,
            prior_delayed_invoice_count=req.num_late_payments,
            payment_after_followup_count=req.payment_after_followup_count,
            total_invoices=req.total_invoices,
            deterioration_trend=req.deterioration_trend,
            invoice_acknowledgement_behavior=req.invoice_acknowledgement_behavior,
            transaction_success_failure_pattern=req.transaction_success_failure_pattern,
        )
        behavior = await self.behavior_svc.analyze(behavior_req)

        # ── Step 2: Delay Prediction (enriched with behavior) ─────────────────
        avg_invoice = req.invoice_amount  # fallback — no portfolio avg in request
        delay_req = DelayPredictionRequest(
            invoice_id=req.invoice_id,
            invoice_amount=req.invoice_amount,
            days_overdue=req.days_overdue,
            payment_terms=req.payment_terms,
            customer_avg_invoice_amount=avg_invoice,
            customer_credit_score=req.customer_credit_score,
            customer_avg_days_to_pay=req.customer_avg_days_to_pay,
            num_late_payments=req.num_late_payments,
            customer_total_overdue=req.customer_total_overdue,
            # Feed behavior outputs
            behavior_type=behavior.behavior_type,
            on_time_ratio=behavior.on_time_ratio,
            avg_delay_days_historical=behavior.avg_delay_days,
            behavior_risk_score=behavior.behavior_risk_score,
            deterioration_trend=req.deterioration_trend,
            followup_dependency=behavior.followup_dependency,
        )
        delay = await self.delay_svc.predict(delay_req)

        # ── Step 3: Collection Strategy ───────────────────────────────────────
        strategy_req = StrategyRequest(
            invoice_id=req.invoice_id,
            customer_name=req.customer_name,
            invoice_amount=req.invoice_amount,
            days_overdue=req.days_overdue,
            delay_probability=delay.delay_probability,
            risk_tier=delay.risk_tier,
            recoverability_score=max(0.1, 1.0 - delay.delay_probability),
            nach_applicable=behavior.nach_recommended,
            borrower_type="corporate",
            automation_feasible=delay.risk_tier != "High",
            behavior_type=behavior.behavior_type,
            followup_dependency=behavior.followup_dependency,
        )
        strategy = self.strategy_svc.optimize(strategy_req)

        # ── Step 4: GPT-4o Business Summary ───────────────────────────────────
        business_summary = await self._generate_summary(req, behavior, delay, strategy)

        return AgentCaseResponse(
            invoice_id=req.invoice_id,
            payment_behavior=behavior,
            delay_prediction=delay,
            strategy=strategy,
            business_summary=business_summary,
            recommended_action=strategy.recommended_action,
            model_used=self.model,
        )

    async def _generate_summary(self, req, behavior, delay, strategy) -> str:
        """Generate a GPT-4o business narrative. Falls back to template on error."""
        prompt = f"""
Case Report:
- Customer: {req.customer_name} | Industry: {req.industry}
- Invoice: {req.invoice_id} | Amount: ${req.invoice_amount:,.0f} | Days Overdue: {req.days_overdue}
- Payment Behavior: {behavior.behavior_type} | On-time ratio: {behavior.on_time_ratio:.0f}% | Trend: {behavior.trend}
- Delay Probability: {delay.delay_probability:.0%} | Risk Tier: {delay.risk_tier} | Score: {delay.risk_score}/100
- Top Drivers: {'; '.join(delay.top_drivers[:3])}
- Strategy: {strategy.recommended_action} | Urgency: {strategy.urgency} | Channel: {strategy.channel}
- NACH Recommended: {behavior.nach_recommended}

Write a business summary for the collections manager.
""".strip()

        try:
            resp = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("GPT-4o summary failed (%s) — using template", exc)
            return self._template_summary(req, behavior, delay, strategy)

    def _template_summary(self, req, behavior, delay, strategy) -> str:
        return (
            f"{req.customer_name} is a '{behavior.behavior_type}' with an on-time payment ratio "
            f"of {behavior.on_time_ratio:.0f}% and a {behavior.trend.lower()} trend. "
            f"The invoice of ${req.invoice_amount:,.0f} (overdue {req.days_overdue} days) carries a "
            f"{delay.delay_probability:.0%} delay probability, placing it in the {delay.risk_tier} risk tier. "
            f"Recommended action: {strategy.recommended_action} via {strategy.channel} "
            f"within {strategy.next_action_in_hours} hours. "
            f"Key drivers: {'; '.join(delay.top_drivers[:2])}."
        )
