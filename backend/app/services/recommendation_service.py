"""
OpenAI prescriptive analytics agent.

Receives invoice context + ML predictions and uses GPT-4o to generate
a structured collection recommendation with reasoning.
"""

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an expert Accounts Receivable collections strategist with 20 years of experience.
You analyze invoice data, ML model predictions, and customer payment history to generate precise,
actionable collection strategies.

Always respond with a valid JSON object matching this exact schema:
{
  "recommended_action": "<action string>",
  "priority": "<Critical|High|Medium|Low>",
  "timeline": "<timeline string>",
  "reasoning": "<1-3 sentence explanation>",
  "additional_notes": "<optional extra context>"
}

Recommended action options (choose the most appropriate):
- "Send Payment Reminder Email"
- "Make Collection Call"
- "Send Formal Demand Letter"
- "Offer Early Payment Discount"
- "Escalate to Collections Agency"
- "Initiate Legal Action Review"
- "Put Account on Credit Hold"
- "Schedule Payment Plan Discussion"
- "Send Final Notice"

Priority levels:
- Critical: >₹50L overdue OR >90 days OR high risk with >80% delay probability
- High: >₹20L OR >45 days OR high risk
- Medium: >₹5L OR >15 days OR medium risk
- Low: recent invoice, low risk, good payment history
"""


class RecommendationService:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        Run the GPT-4o collection agent.

        Builds a rich context prompt from prediction outputs and customer history,
        then parses the structured JSON response.
        """
        user_prompt = self._build_prompt(request)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Low temperature for consistent, factual outputs
                max_tokens=500,
            )

            content = response.choices[0].message.content
            data = json.loads(content)

            return RecommendationResponse(
                invoice_id=request.invoice_id,
                recommended_action=data.get("recommended_action", "Send Payment Reminder Email"),
                priority=data.get("priority", "Medium"),
                timeline=data.get("timeline", "Within 5 Business Days"),
                reasoning=data.get("reasoning", ""),
                additional_notes=data.get("additional_notes"),
                model_used=self.model,
            )

        except Exception as exc:
            logger.error("OpenAI recommendation failed: %s", exc)
            return self._fallback_recommendation(request)

    def _build_prompt(self, req: RecommendationRequest) -> str:
        """Compose the detailed context prompt for the GPT-4o agent."""
        hist = req.customer_history
        return f"""
Analyze this invoice and generate a collection strategy.

INVOICE DETAILS:
- Invoice ID: {req.invoice_id}
- Amount: ${req.invoice_amount:,.2f}
- Days Overdue: {req.days_overdue}
- Risk Classification: {req.risk_label}

ML PREDICTION OUTPUTS:
- Probability of payment in 7 days:  {req.pay_7_days:.1%}
- Probability of payment in 15 days: {req.pay_15_days:.1%}
- Probability of payment in 30 days: {req.pay_30_days:.1%}

CUSTOMER PROFILE:
- Customer: {hist.customer_name}
- Industry: {hist.industry}
- Credit Score: {hist.credit_score}
- Average Days to Pay: {hist.avg_days_to_pay:.1f}
- Number of Late Payments (historical): {hist.num_late_payments}
- Number of Disputes (historical): {hist.num_disputes}
- Total Outstanding Balance: ${hist.total_outstanding:,.2f}

Based on this data, provide a precise collection recommendation as JSON.
""".strip()

    def _fallback_recommendation(self, req: RecommendationRequest) -> RecommendationResponse:
        """Rule-based fallback when OpenAI is unavailable."""
        if req.risk_label == "High" or req.days_overdue > 60:
            action = "Send Formal Demand Letter"
            priority = "Critical" if req.invoice_amount > 50000 else "High"
            timeline = "Within 24 Hours"
        elif req.risk_label == "Medium" or req.days_overdue > 30:
            action = "Make Collection Call"
            priority = "High"
            timeline = "Within 48 Hours"
        else:
            action = "Send Payment Reminder Email"
            priority = "Medium"
            timeline = "Within 5 Business Days"

        return RecommendationResponse(
            invoice_id=req.invoice_id,
            recommended_action=action,
            priority=priority,
            timeline=timeline,
            reasoning=(
                f"Invoice is {req.days_overdue} days overdue with {req.risk_label} risk. "
                f"Delay probability is {1 - req.pay_30_days:.0%}."
            ),
            model_used="rule-based-fallback",
        )
