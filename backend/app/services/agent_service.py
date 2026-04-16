"""
Agentic Collections Intelligence Service — OpenAI Function Calling.

Architecture: ReAct loop (Reason → Act → Observe → Reason...)
  GPT-4o decides WHICH tools to call, IN WHAT ORDER, and HOW MANY TIMES
  based on what it discovers at each step — not a fixed hardcoded sequence.

Tools exposed to the agent:
  1. analyze_payment_behavior   → BehaviorService
  2. predict_invoice_delay      → DelayService
  3. optimize_collection_strategy → StrategyService
  4. get_borrower_risk          → BorrowerService
  5. get_portfolio_summary      → CashflowService / mock_data
  6. get_invoice_details        → mock_data lookup

Max iterations: 8 (safety guard against infinite loops)
Falls back to rule-based pipeline if OpenAI is unavailable.
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import get_settings
from app.schemas.agent import (
    AgentAskRequest,
    AgentAskResponse,
    AgentCaseRequest,
    AgentCaseResponse,
    AgentToolCall,
)
from app.schemas.behavior import PaymentBehaviorRequest
from app.schemas.borrower import BorrowerPredictionRequest
from app.schemas.delay import DelayPredictionRequest
from app.schemas.strategy import StrategyRequest
from app.services.behavior_service import BehaviorService
from app.services.borrower_service import BorrowerService
from app.services.cashflow_service import CashflowService
from app.services.delay_service import DelayService
from app.services.enrichment_service import EnrichmentService
from app.services.interaction_service import InteractionService
from app.services.sentinel_service import SentinelService
from app.services.strategy_service import StrategyService
from app.utils.mock_data import MOCK_INVOICES, get_portfolio_summary

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_ITERATIONS = 8

# ── System prompt ─────────────────────────────────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are an autonomous AI collections analyst with access to tools.
Your job: analyze invoices and borrowers to help a collections manager decide what to do.

How to behave:
- Think step by step before calling any tool.
- ALWAYS check payment behavior before predicting delay (behavior feeds the delay model).
- ALWAYS predict delay before recommending collection strategy.
- For HIGH or CRITICAL risk cases, ALWAYS call check_external_signals for external red flags.
- ALWAYS call get_interaction_history to understand what actions have already been tried and what worked.
- Use get_borrower_enrichment to check MCA/GST/EPFO/bureau/legal health when risk is High or Critical.
- Use get_borrower_risk when the question is about a customer holistically.
- Use get_portfolio_summary only when asked about the full portfolio.
- If interaction history shows broken PTP + no answer pattern, escalate strategy severity.
- If enrichment shows NCLT risk or GST suspension, escalate to Critical and recommend legal action.
- After gathering data, synthesize a clear, direct, actionable recommendation grounded in evidence.
- Be concise. No jargon. Speak like a senior analyst briefing a busy manager.

When you have enough information, stop calling tools and write your final answer."""

# ── Tool definitions (OpenAI function calling schema) ─────────────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_payment_behavior",
            "description": (
                "Analyzes a borrower's historical payment personality. "
                "Returns behavior_type (e.g. Chronic Delayed Payer), on_time_ratio, "
                "avg_delay_days, trend, behavior_risk_score, followup_dependency, nach_recommended. "
                "Call this FIRST before predicting delay."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Borrower customer ID"},
                    "customer_name": {"type": "string", "description": "Borrower name"},
                    "historical_on_time_ratio": {
                        "type": "number",
                        "description": "Fraction of invoices paid on time (0–1). Default 0.7."
                    },
                    "avg_delay_days": {
                        "type": "number",
                        "description": "Average days late on historical payments. Default 10."
                    },
                    "repayment_consistency": {
                        "type": "number",
                        "description": "How consistent their payment timing is (0–1). Default 0.6."
                    },
                    "partial_payment_frequency": {
                        "type": "number",
                        "description": "How often they pay partial amounts (0–1). Default 0.1."
                    },
                    "prior_delayed_invoice_count": {
                        "type": "integer",
                        "description": "Count of historically delayed invoices. Default 0."
                    },
                    "payment_after_followup_count": {
                        "type": "integer",
                        "description": "How many times they needed a reminder to pay. Default 0."
                    },
                    "total_invoices": {
                        "type": "integer",
                        "description": "Total invoices in history. Default 10."
                    },
                    "deterioration_trend": {
                        "type": "number",
                        "description": "Payment trend: -1=improving, 0=stable, +1=worsening. Default 0."
                    },
                },
                "required": ["customer_id", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "predict_invoice_delay",
            "description": (
                "Predicts delay probability for a specific invoice. "
                "Returns delay_probability, risk_score (0–100), risk_tier (High/Medium/Low), "
                "top_drivers explaining WHY the invoice is at risk. "
                "Enriches prediction with behavior context if provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string", "description": "Invoice ID"},
                    "invoice_amount": {"type": "number", "description": "Invoice amount in INR"},
                    "days_overdue": {"type": "integer", "description": "Days overdue (0 if current)"},
                    "payment_terms": {"type": "integer", "description": "Payment terms in days (e.g. 30, 60)"},
                    "customer_credit_score": {
                        "type": "integer",
                        "description": "Customer credit score 300–850"
                    },
                    "customer_avg_days_to_pay": {
                        "type": "number",
                        "description": "Customer's historical avg days to pay"
                    },
                    "num_late_payments": {"type": "integer", "description": "Number of prior late payments"},
                    "customer_total_overdue": {
                        "type": "number",
                        "description": "Total overdue amount across all customer invoices"
                    },
                    "behavior_type": {
                        "type": "string",
                        "description": "Optional: behavior_type from analyze_payment_behavior"
                    },
                    "behavior_risk_score": {
                        "type": "number",
                        "description": "Optional: behavior_risk_score from analyze_payment_behavior"
                    },
                    "on_time_ratio": {
                        "type": "number",
                        "description": "Optional: on_time_ratio from analyze_payment_behavior"
                    },
                    "avg_delay_days_historical": {
                        "type": "number",
                        "description": "Optional: avg_delay_days from analyze_payment_behavior"
                    },
                    "followup_dependency": {
                        "type": "boolean",
                        "description": "Optional: followup_dependency from analyze_payment_behavior"
                    },
                },
                "required": [
                    "invoice_id", "invoice_amount", "days_overdue",
                    "customer_credit_score", "customer_avg_days_to_pay",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_collection_strategy",
            "description": (
                "Determines the best collection action for an invoice. "
                "Returns priority_score, urgency (Critical/High/Medium/Low), "
                "recommended_action, channel (Call/Email/Legal), next_action_in_hours, reason. "
                "Requires delay_probability and risk_tier from predict_invoice_delay."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "invoice_amount": {"type": "number"},
                    "days_overdue": {"type": "integer"},
                    "delay_probability": {
                        "type": "number",
                        "description": "delay_probability from predict_invoice_delay (0–1)"
                    },
                    "risk_tier": {
                        "type": "string",
                        "description": "risk_tier from predict_invoice_delay: High | Medium | Low"
                    },
                    "nach_applicable": {
                        "type": "boolean",
                        "description": "Whether NACH mandate is applicable for this borrower"
                    },
                    "behavior_type": {
                        "type": "string",
                        "description": "Optional behavior_type from analyze_payment_behavior"
                    },
                    "followup_dependency": {
                        "type": "boolean",
                        "description": "Optional followup_dependency from analyze_payment_behavior"
                    },
                },
                "required": [
                    "invoice_id", "customer_name", "invoice_amount",
                    "days_overdue", "delay_probability", "risk_tier",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_borrower_risk",
            "description": (
                "Aggregates ALL open invoices for a customer and returns borrower-level risk: "
                "total_outstanding, weighted_delay_probability, borrower_risk_score (0–100), "
                "borrower_risk_tier, expected_recovery_amount, at_risk_amount, "
                "escalation_recommended, relationship_action. "
                "Use when asked about a customer holistically, not just one invoice."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "customer_name": {"type": "string"},
                },
                "required": ["customer_id", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoice_details",
            "description": (
                "Fetches raw facts about a specific invoice: amount, status, days_overdue, "
                "credit_score, risk_label, payment_terms, pay probabilities. "
                "Use this when you need invoice context before calling other tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string", "description": "Invoice ID e.g. INV-2024-001"},
                },
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": (
                "Returns a high-level summary of the entire AR portfolio: "
                "total_invoices, total_outstanding, overdue_count, overdue_amount, "
                "amount_at_risk, high_risk_count, risk_breakdown. "
                "Use only for portfolio-wide questions."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_external_signals",
            "description": (
                "Sentinel Engine: checks external risk signals for a customer. "
                "Returns is_flagged, risk_level, overall_sentinel_score, and a list of signals "
                "such as leadership changes, news alerts (NCLT/regulatory), AP contact failures, "
                "email anomalies, and sector distress. "
                "ALWAYS call this for High or Critical risk customers before finalizing strategy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID to check"},
                    "customer_name": {"type": "string", "description": "Customer name"},
                },
                "required": ["customer_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_interaction_history",
            "description": (
                "Fetches the full collections interaction history for an invoice: "
                "all calls made, emails sent, PTPs given and broken, field visits, legal notices. "
                "Returns action_effectiveness (which actions worked best), best_action recommendation "
                "derived from past outcomes, total amount recovered so far, and learning_confidence_boost. "
                "ALWAYS call this to understand what has already been tried before recommending the next action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string", "description": "Invoice ID to get history for"},
                },
                "required": ["invoice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_borrower_enrichment",
            "description": (
                "Fetches CredCheck enrichment data for a borrower: "
                "MCA compliance status, GST filing health, EPFO workforce stability, "
                "bureau/credit health summary, legal profile, and data availability flags "
                "(has_bureau_data, has_gst_data, has_legal_data). "
                "Use when you need deeper borrower health signals beyond payment history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID"},
                },
                "required": ["customer_id"],
            },
        },
    },
]


class AgentService:

    def __init__(self) -> None:
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.behavior_svc = BehaviorService()
        self.delay_svc = DelayService()
        self.strategy_svc = StrategyService()
        self.borrower_svc = BorrowerService()
        self.cashflow_svc = CashflowService()
        self.sentinel_svc = SentinelService()
        self.interaction_svc = InteractionService()
        self.enrichment_svc = EnrichmentService()

    # ── Public: structured case (backward compatible) ─────────────────────────

    async def analyze_case(self, req: AgentCaseRequest) -> AgentCaseResponse:
        """
        True agentic analysis of one invoice case.
        GPT-4o drives which tools to call and in what order via function calling.
        Falls back to fixed pipeline if OpenAI unavailable.
        """
        initial_prompt = (
            f"Analyze invoice {req.invoice_id} for customer {req.customer_name} "
            f"(customer_id={req.customer_id}).\n"
            f"Invoice amount: ${req.invoice_amount:,.0f}, "
            f"Days overdue: {req.days_overdue}, "
            f"Payment terms: {req.payment_terms}d, "
            f"Industry: {req.industry}, "
            f"Credit score: {req.customer_credit_score}, "
            f"Avg days to pay: {req.customer_avg_days_to_pay}d, "
            f"Late payments: {req.num_late_payments}.\n"
            f"Historical on-time ratio: {req.historical_on_time_ratio:.0%}, "
            f"Avg historical delay: {req.avg_delay_days}d.\n\n"
            f"Provide a full intelligence analysis: behavior → delay prediction → "
            f"collection strategy → business recommendation."
        )

        trace, final_answer, iterations = await self._react_loop(initial_prompt)

        # Extract structured outputs from trace (or fall back to rule engine)
        behavior = self._extract_tool_output(trace, "analyze_payment_behavior")
        delay = self._extract_tool_output(trace, "predict_invoice_delay")
        strategy_out = self._extract_tool_output(trace, "optimize_collection_strategy")

        # If agent didn't call a tool, run rule-based fallbacks
        if behavior is None:
            behavior = await self._fallback_behavior(req)
        if delay is None:
            delay = await self._fallback_delay(req, behavior)
        if strategy_out is None:
            strategy_out = self._fallback_strategy(req, delay, behavior)

        # Convert raw dicts → typed Pydantic objects
        from app.schemas.behavior import PaymentBehaviorResponse
        from app.schemas.delay import DelayPredictionResponse, DelayDriver
        from app.schemas.strategy import StrategyResponse

        behavior_resp = (
            PaymentBehaviorResponse(**behavior)
            if isinstance(behavior, dict) else behavior
        )
        delay_resp = (
            DelayPredictionResponse(**{
                **delay,
                "detailed_drivers": [
                    DelayDriver(**d) if isinstance(d, dict) else d
                    for d in delay.get("detailed_drivers", [])
                ]
            })
            if isinstance(delay, dict) else delay
        )
        strategy_resp = (
            StrategyResponse(**strategy_out)
            if isinstance(strategy_out, dict) else strategy_out
        )

        tools_called = [t.tool_name for t in trace]

        return AgentCaseResponse(
            invoice_id=req.invoice_id,
            payment_behavior=behavior_resp,
            delay_prediction=delay_resp,
            strategy=strategy_resp,
            business_summary=final_answer,
            recommended_action=strategy_resp.recommended_action,
            model_used=self.model,
            reasoning_trace=trace,
            agent_iterations=iterations,
            tools_called=tools_called,
        )

    # ── Public: free-form agentic question ────────────────────────────────────

    async def ask(self, req: AgentAskRequest) -> AgentAskResponse:
        """
        Answer a free-form question by autonomously calling tools.
        E.g. 'Which borrowers need escalation today?' or 'Analyze INV-2024-004'
        """
        context_parts = [req.question]
        if req.invoice_id:
            context_parts.append(f"(Focus on invoice: {req.invoice_id})")
        if req.customer_id:
            context_parts.append(f"(Customer ID: {req.customer_id})")

        prompt = " ".join(context_parts)
        trace, final_answer, iterations = await self._react_loop(prompt)

        return AgentAskResponse(
            answer=final_answer,
            reasoning_trace=trace,
            tools_called=[t.tool_name for t in trace],
            iterations=iterations,
            model_used=self.model,
        )

    # ── Core ReAct Loop ───────────────────────────────────────────────────────

    async def _react_loop(
        self, user_prompt: str
    ) -> tuple[list[AgentToolCall], str, int]:
        """
        The ReAct loop: GPT-4o reasons → calls tools → observes results → reasons again.
        Terminates when GPT-4o gives a final text answer (finish_reason == "stop")
        or when MAX_ITERATIONS is reached.
        """
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        trace: list[AgentToolCall] = []
        step = 0

        try:
            for iteration in range(MAX_ITERATIONS):
                response = await self.openai.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=1000,
                )

                msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                # Append GPT's response to conversation history
                messages.append(msg.model_dump(exclude_unset=True))  # type: ignore[arg-type]

                # Agent chose to stop — has enough info to answer
                if finish_reason == "stop":
                    final_text = msg.content or "Analysis complete."
                    return trace, final_text, iteration + 1

                # Agent called one or more tools
                if not msg.tool_calls:
                    return trace, msg.content or "Analysis complete.", iteration + 1

                # Execute each tool call GPT requested
                tool_results: list[ChatCompletionMessageParam] = []
                for tc in msg.tool_calls:
                    step += 1
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Extract GPT's "thought" from any preceding text content
                    thought = msg.content or None

                    # Execute the tool
                    tool_output = await self._dispatch_tool(fn_name, fn_args)

                    # Record in trace
                    trace.append(
                        AgentToolCall(
                            step=step,
                            tool_name=fn_name,
                            tool_input=fn_args,
                            tool_output=tool_output,
                            agent_thought=thought,
                        )
                    )

                    # Add tool result to conversation so GPT can reason over it
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_output),
                    })

                messages.extend(tool_results)

            # Hit max iterations — ask GPT to summarize what it found
            messages.append({
                "role": "user",
                "content": (
                    "You have reached the maximum number of tool calls. "
                    "Based on everything you have gathered so far, "
                    "provide your final analysis and recommendation."
                ),
            })
            final_resp = await self.openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                max_tokens=600,
            )
            return trace, final_resp.choices[0].message.content or "", MAX_ITERATIONS

        except Exception as exc:
            logger.warning("OpenAI agent failed (%s) — falling back to rule pipeline", exc)
            return trace, "", 0

    # ── Tool dispatcher ───────────────────────────────────────────────────────

    async def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Route a tool call from GPT-4o to the correct service."""
        try:
            if name == "analyze_payment_behavior":
                return await self._tool_behavior(args)
            if name == "predict_invoice_delay":
                return await self._tool_delay(args)
            if name == "optimize_collection_strategy":
                return self._tool_strategy(args)
            if name == "get_borrower_risk":
                return self._tool_borrower_risk(args)
            if name == "get_invoice_details":
                return self._tool_invoice_details(args)
            if name == "get_portfolio_summary":
                return get_portfolio_summary()
            if name == "check_external_signals":
                return self._tool_sentinel(args)
            if name == "get_interaction_history":
                return self._tool_interactions(args)
            if name == "get_borrower_enrichment":
                return self._tool_enrichment(args)
            return {"error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.error("Tool %s failed: %s", name, exc)
            return {"error": str(exc)}

    # ── Individual tool implementations ───────────────────────────────────────

    async def _tool_behavior(self, args: dict) -> dict:
        req = PaymentBehaviorRequest(
            customer_id=args.get("customer_id", "unknown"),
            customer_name=args.get("customer_name", "Unknown"),
            historical_on_time_ratio=float(args.get("historical_on_time_ratio", 0.7)),
            avg_delay_days=float(args.get("avg_delay_days", 10.0)),
            repayment_consistency=float(args.get("repayment_consistency", 0.6)),
            partial_payment_frequency=float(args.get("partial_payment_frequency", 0.1)),
            prior_delayed_invoice_count=int(args.get("prior_delayed_invoice_count", 0)),
            payment_after_followup_count=int(args.get("payment_after_followup_count", 0)),
            total_invoices=int(args.get("total_invoices", 10)),
            deterioration_trend=float(args.get("deterioration_trend", 0.0)),
        )
        result = await self.behavior_svc.analyze(req)
        return result.model_dump()

    async def _tool_delay(self, args: dict) -> dict:
        req = DelayPredictionRequest(
            invoice_id=args["invoice_id"],
            invoice_amount=float(args["invoice_amount"]),
            days_overdue=int(args.get("days_overdue", 0)),
            payment_terms=int(args.get("payment_terms", 30)),
            customer_avg_invoice_amount=float(args.get("invoice_amount", 0)),
            customer_credit_score=int(args.get("customer_credit_score", 650)),
            customer_avg_days_to_pay=float(args.get("customer_avg_days_to_pay", 30)),
            num_late_payments=int(args.get("num_late_payments", 0)),
            customer_total_overdue=float(args.get("customer_total_overdue", 0)),
            behavior_type=args.get("behavior_type"),
            on_time_ratio=args.get("on_time_ratio"),
            avg_delay_days_historical=args.get("avg_delay_days_historical"),
            behavior_risk_score=args.get("behavior_risk_score"),
            deterioration_trend=args.get("deterioration_trend"),
            followup_dependency=args.get("followup_dependency"),
        )
        result = await self.delay_svc.predict(req)
        return result.model_dump()

    def _tool_strategy(self, args: dict) -> dict:
        req = StrategyRequest(
            invoice_id=args["invoice_id"],
            customer_name=args["customer_name"],
            invoice_amount=float(args["invoice_amount"]),
            days_overdue=int(args.get("days_overdue", 0)),
            delay_probability=float(args["delay_probability"]),
            risk_tier=args["risk_tier"],
            recoverability_score=max(0.1, 1.0 - float(args["delay_probability"])),
            nach_applicable=bool(args.get("nach_applicable", False)),
            automation_feasible=args.get("risk_tier", "Low") != "High",
            behavior_type=args.get("behavior_type"),
            followup_dependency=args.get("followup_dependency"),
        )
        result = self.strategy_svc.optimize(req)
        return result.model_dump()

    def _tool_borrower_risk(self, args: dict) -> dict:
        # Look up customer info from MOCK_INVOICES
        customer_id = str(args.get("customer_id", ""))
        customer_invoices = [
            inv for inv in MOCK_INVOICES
            if str(inv["customer_id"]) == customer_id
            and inv["status"] in ("open", "overdue")
        ]
        sample = customer_invoices[0] if customer_invoices else {}

        portfolio_total = sum(
            inv["amount"] for inv in MOCK_INVOICES
            if inv["status"] in ("open", "overdue")
        )
        req = BorrowerPredictionRequest(
            customer_id=customer_id,
            customer_name=args.get("customer_name", sample.get("customer_name", "Unknown")),
            industry=sample.get("industry", "unknown"),
            credit_score=sample.get("credit_score", 650),
            avg_days_to_pay=sample.get("avg_days_to_pay", 30.0),
            num_late_payments=sample.get("num_late_payments", 0),
        )
        result = self.borrower_svc.predict_borrower(req, portfolio_total=portfolio_total)
        return result.model_dump()

    def _tool_invoice_details(self, args: dict) -> dict:
        invoice_id = args.get("invoice_id", "")
        for inv in MOCK_INVOICES:
            if inv["invoice_id"] == invoice_id:
                return {
                    "invoice_id": inv["invoice_id"],
                    "customer_id": str(inv["customer_id"]),
                    "customer_name": inv["customer_name"],
                    "industry": inv.get("industry", "unknown"),
                    "amount": inv["amount"],
                    "status": inv["status"],
                    "days_overdue": inv.get("days_overdue", 0),
                    "risk_label": inv.get("risk_label", "Medium"),
                    "credit_score": inv.get("credit_score", 650),
                    "avg_days_to_pay": inv.get("avg_days_to_pay", 30),
                    "num_late_payments": inv.get("num_late_payments", 0),
                    "payment_terms": inv.get("payment_terms", 30),
                    "customer_total_overdue": inv.get("customer_total_overdue", 0),
                    "pay_7_days": inv.get("pay_7_days", 0),
                    "pay_15_days": inv.get("pay_15_days", 0),
                    "pay_30_days": inv.get("pay_30_days", 0),
                    "recommended_action": inv.get("recommended_action", ""),
                }
        return {"error": f"Invoice {invoice_id} not found"}

    def _tool_interactions(self, args: dict) -> dict:
        invoice_id = str(args.get("invoice_id", ""))
        result = self.interaction_svc.get_by_invoice(invoice_id)
        return {
            "invoice_id": result.invoice_id,
            "total_interactions": result.total_interactions,
            "total_recovered": result.total_recovered,
            "has_broken_ptp": result.has_broken_ptp,
            "open_ptp_amount": result.open_ptp_amount,
            "best_action": result.best_action,
            "learning_confidence_boost": result.learning_confidence_boost,
            "action_effectiveness": [
                {
                    "action_type": e.action_type,
                    "success_rate": e.success_rate,
                    "total_attempts": e.total_attempts,
                    "recommended": e.recommended,
                }
                for e in result.action_effectiveness
            ],
            "recent_interactions": [
                {
                    "date": i.date,
                    "action_type": i.action_type,
                    "outcome": i.outcome,
                    "notes": i.notes,
                    "broken_ptp": i.broken_ptp,
                }
                for i in result.interactions[-3:]  # last 3 touchpoints
            ],
        }

    def _tool_enrichment(self, args: dict) -> dict:
        customer_id = str(args.get("customer_id", ""))
        result = self.enrichment_svc.get_enrichment(customer_id)
        return {
            "customer_id": result.customer_id,
            "customer_name": result.customer_name,
            "enrichment_score": result.enrichment_score,
            "enrichment_label": result.enrichment_label,
            "risk_flags": result.risk_flags,
            "mca_status": result.mca.mca_status,
            "mca_compliance_score": result.mca.compliance_score,
            "gst_filing_score": result.gst.filing_score,
            "gst_delay_band": result.gst.delay_band,
            "bureau_score": result.bureau.bureau_score,
            "credit_health": result.bureau.credit_health_label,
            "dpd_classification": result.bureau.dpd_classification,
            "legal_risk": result.legal.legal_risk_label,
            "nclt_risk": result.legal.nclt_risk,
            "epfo_trend": result.epfo.pf_trend,
            "data_availability": {
                "has_bureau_data": result.data_availability.has_bureau_data,
                "has_gst_data": result.data_availability.has_gst_data,
                "has_legal_data": result.data_availability.has_legal_data,
                "has_mca_data": result.data_availability.has_mca_data,
                "completeness_score": result.data_availability.completeness_score,
            },
        }

    def _tool_sentinel(self, args: dict) -> dict:
        customer_id = str(args.get("customer_id", ""))
        result = self.sentinel_svc.check_customer(customer_id)
        return {
            "customer_id": result.customer_id,
            "customer_name": result.customer_name,
            "is_flagged": result.is_flagged,
            "risk_level": result.risk_level,
            "overall_sentinel_score": result.overall_sentinel_score,
            "recommendation": result.recommendation,
            "high_signal_count": result.high_signal_count,
            "medium_signal_count": result.medium_signal_count,
            "signals": [
                {
                    "signal_type": s.signal_type,
                    "severity": s.severity,
                    "description": s.description,
                    "source": s.source,
                }
                for s in result.signals
            ],
        }

    # ── Helpers for extracting typed outputs from trace ───────────────────────

    def _extract_tool_output(
        self, trace: list[AgentToolCall], tool_name: str
    ) -> dict | None:
        for step in trace:
            if step.tool_name == tool_name and "error" not in step.tool_output:
                return step.tool_output
        return None

    # ── Rule-based fallbacks (used when OpenAI is unavailable) ────────────────

    async def _fallback_behavior(self, req: AgentCaseRequest):
        beh_req = PaymentBehaviorRequest(
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
        )
        return await self.behavior_svc.analyze(beh_req)

    async def _fallback_delay(self, req: AgentCaseRequest, behavior):
        from app.schemas.behavior import PaymentBehaviorResponse
        b = behavior if isinstance(behavior, object) and not isinstance(behavior, dict) \
            else type("B", (), behavior)()
        delay_req = DelayPredictionRequest(
            invoice_id=req.invoice_id,
            invoice_amount=req.invoice_amount,
            days_overdue=req.days_overdue,
            payment_terms=req.payment_terms,
            customer_avg_invoice_amount=req.invoice_amount,
            customer_credit_score=req.customer_credit_score,
            customer_avg_days_to_pay=req.customer_avg_days_to_pay,
            num_late_payments=req.num_late_payments,
            customer_total_overdue=req.customer_total_overdue,
            behavior_type=getattr(b, "behavior_type", None),
            on_time_ratio=getattr(b, "on_time_ratio", None),
            avg_delay_days_historical=getattr(b, "avg_delay_days", None),
            behavior_risk_score=getattr(b, "behavior_risk_score", None),
            deterioration_trend=req.deterioration_trend,
            followup_dependency=getattr(b, "followup_dependency", None),
        )
        return await self.delay_svc.predict(delay_req)

    def _fallback_strategy(self, req: AgentCaseRequest, delay, behavior):
        strat_req = StrategyRequest(
            invoice_id=req.invoice_id,
            customer_name=req.customer_name,
            invoice_amount=req.invoice_amount,
            days_overdue=req.days_overdue,
            delay_probability=getattr(delay, "delay_probability", 0.5),
            risk_tier=getattr(delay, "risk_tier", "Medium"),
            recoverability_score=max(0.1, 1.0 - getattr(delay, "delay_probability", 0.5)),
            nach_applicable=getattr(behavior, "nach_recommended", False),
            automation_feasible=getattr(delay, "risk_tier", "Low") != "High",
            behavior_type=getattr(behavior, "behavior_type", None),
            followup_dependency=getattr(behavior, "followup_dependency", None),
        )
        return self.strategy_svc.optimize(strat_req)
