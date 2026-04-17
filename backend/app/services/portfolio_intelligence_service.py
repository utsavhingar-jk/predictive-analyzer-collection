"""Shared portfolio intelligence pipeline for predictive AR workflows."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.behavior import PaymentBehaviorRequest, PaymentBehaviorResponse
from app.schemas.delay import DelayPredictionRequest, DelayPredictionResponse
from app.schemas.prediction import (
    DefaultPredictionRequest,
    DefaultPredictionResponse,
    PaymentPredictionRequest,
    PaymentPredictionResponse,
    PrioritizedInvoice,
)
from app.schemas.strategy import StrategyRequest, StrategyResponse
from app.services.behavior_service import BehaviorService
from app.services.delay_service import DelayService
from app.services.json_data import load_invoices_from_json
from app.services.prediction_service import PredictionService
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)

# Module-level thread pool used by _run_sync so we don't create/destroy
# a new OS thread on every synchronous portfolio call.
_SYNC_THREAD_POOL = ThreadPoolExecutor(max_workers=1)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _to_date(value: Any, default: date) -> date:
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return default
    return default


@dataclass
class PortfolioInvoiceResult:
    invoice: dict[str, Any]
    payment_request: PaymentPredictionRequest
    behavior_request: PaymentBehaviorRequest
    payment: PaymentPredictionResponse
    default: DefaultPredictionResponse
    behavior: PaymentBehaviorResponse
    delay: DelayPredictionResponse
    strategy: StrategyResponse

    def cumulative_payment_probabilities(self) -> tuple[float, float, float]:
        pay_7 = _clamp(float(self.payment.pay_7_days or 0.0), 0.0, 1.0)
        pay_15 = max(pay_7, _clamp(float(self.payment.pay_15_days or 0.0), 0.0, 1.0))
        pay_30 = max(pay_15, _clamp(float(self.payment.pay_30_days or 0.0), 0.0, 1.0))
        return pay_7, pay_15, pay_30

    def incremental_payment_probabilities(self) -> tuple[float, float, float, float]:
        pay_7, pay_15, pay_30 = self.cumulative_payment_probabilities()
        return (
            pay_7,
            max(pay_15 - pay_7, 0.0),
            max(pay_30 - pay_15, 0.0),
            max(1.0 - pay_30, 0.0),
        )

    def expected_remaining_days(self) -> float:
        pay_7, pay_15, pay_30 = self.cumulative_payment_probabilities()
        tail_days = 45.0 + min(max(int(self.invoice.get("days_overdue") or 0), 0), 30) * 0.25
        return (
            pay_7 * 3.5
            + max(pay_15 - pay_7, 0.0) * 11.0
            + max(pay_30 - pay_15, 0.0) * 22.5
            + max(1.0 - pay_30, 0.0) * tail_days
        )

    def current_age_days(self) -> int:
        issue_date = self.invoice.get("issue_date") or date.today()
        return max(0, (date.today() - issue_date).days)

    def predicted_collection_age_days(self) -> float:
        return self.current_age_days() + self.expected_remaining_days()

    def portfolio_priority_score(self) -> float:
        return round(
            round(float(self.invoice["amount"]), 2) * round(float(self.delay.delay_probability), 4),
            2,
        )

    def default_probability_value(self) -> float:
        return _clamp(float(self.default.default_probability or 0.0), 0.0, 1.0)

    def as_prioritized_invoice(self) -> PrioritizedInvoice:
        pay_7, pay_15, pay_30 = self.cumulative_payment_probabilities()
        return PrioritizedInvoice(
            invoice_id=str(self.invoice["invoice_id"]),
            customer_name=str(self.invoice["customer_name"]),
            amount=round(float(self.invoice["amount"]), 2),
            days_overdue=int(self.invoice["days_overdue"]),
            risk_label=self.delay.risk_tier,
            delay_probability=round(self.delay.delay_probability, 4),
            priority_score=self.portfolio_priority_score(),
            default_probability=round(self.default_probability_value(), 4),
            default_risk_tier=str(self.default.default_risk_tier),
            recommended_action=self.strategy.recommended_action,
            priority_rank=self.strategy.priority_rank,
            urgency=self.strategy.urgency,
            risk_tier=self.delay.risk_tier,
            behavior_type=self.behavior.behavior_type,
            nach_recommended=bool(
                self.behavior.nach_recommended or self.invoice.get("nach_applicable")
            ),
            pay_7_days=round(pay_7, 4),
            pay_15_days=round(pay_15, 4),
            pay_30_days=round(pay_30, 4),
            delay_confidence=round(self.delay.confidence, 4),
            used_fallback=bool(
                self.payment.used_fallback
                or self.default.used_fallback
                or self.behavior.used_fallback
                or self.delay.used_fallback
            ),
        )

    def as_strategy_response(self) -> StrategyResponse:
        response = self.strategy.model_copy(deep=True)
        response.customer_name = str(self.invoice["customer_name"])
        response.amount = round(float(self.invoice["amount"]), 2)
        response.days_overdue = int(self.invoice["days_overdue"])
        response.risk_label = self.delay.risk_tier
        response.risk_tier = self.delay.risk_tier
        response.delay_probability = round(self.delay.delay_probability, 4)
        response.behavior_type = self.behavior.behavior_type
        response.nach_recommended = bool(
            self.behavior.nach_recommended or self.invoice.get("nach_applicable")
        )
        return response

    def as_invoice_list_item(self) -> dict[str, Any]:
        pay_7, pay_15, pay_30 = self.cumulative_payment_probabilities()
        return {
            "invoice_id": str(self.invoice["invoice_id"]),
            "invoice_number": str(self.invoice["invoice_number"]),
            "customer_id": str(self.invoice["customer_id"]),
            "customer_name": str(self.invoice["customer_name"]),
            "industry": str(self.invoice["industry"]),
            "amount": round(float(self.invoice["amount"]), 2),
            "currency": str(self.invoice.get("currency") or "INR"),
            "issue_date": self.invoice["issue_date"].isoformat(),
            "due_date": self.invoice["due_date"].isoformat(),
            "status": str(self.invoice["status"]),
            "days_overdue": int(self.invoice["days_overdue"]),
            "payment_terms": int(self.invoice["payment_terms"]),
            "credit_score": int(self.invoice["credit_score"]),
            "avg_days_to_pay": round(float(self.invoice["avg_days_to_pay"]), 2),
            "num_late_payments": int(self.invoice["num_late_payments"]),
            "num_previous_invoices": int(self.payment_request.num_previous_invoices),
            "customer_total_overdue": round(float(self.payment_request.customer_total_overdue), 2),
            "risk_label": self.delay.risk_tier,
            "risk_score": int(self.delay.risk_score),
            "pay_7_days": round(pay_7, 4),
            "pay_15_days": round(pay_15, 4),
            "pay_30_days": round(pay_30, 4),
            "delay_probability": round(float(self.delay.delay_probability), 4),
            "default_probability": round(self.default_probability_value(), 4),
            "default_risk_tier": str(self.default.default_risk_tier),
            "priority_score": self.portfolio_priority_score(),
            "priority_rank": self.strategy.priority_rank,
            "urgency": self.strategy.urgency,
            "recommended_action": self.strategy.recommended_action,
            "behavior_type": self.behavior.behavior_type,
            "nach_recommended": bool(
                self.behavior.nach_recommended or self.invoice.get("nach_applicable")
            ),
            "used_fallback": bool(
                self.payment.used_fallback
                or self.default.used_fallback
                or self.behavior.used_fallback
                or self.delay.used_fallback
            ),
        }

    def normalized_payment_prediction_payload(self) -> dict[str, Any]:
        pay_7, pay_15, pay_30 = self.cumulative_payment_probabilities()
        payload = self.payment.model_dump(mode="json")
        payload["pay_7_days"] = round(pay_7, 4)
        payload["pay_15_days"] = round(pay_15, 4)
        payload["pay_30_days"] = round(pay_30, 4)

        normalized_values = {
            "pay_7_days": round(pay_7, 4),
            "pay_15_days": round(pay_15, 4),
            "pay_30_days": round(pay_30, 4),
        }
        payload["feature_drivers_by_horizon"] = [
            {
                **section,
                "predicted_value": normalized_values.get(
                    str(section.get("output_name") or ""),
                    section.get("predicted_value"),
                ),
            }
            for section in (payload.get("feature_drivers_by_horizon") or [])
        ]
        return payload

    def as_invoice_detail(self) -> dict[str, Any]:
        payment_prediction = self.normalized_payment_prediction_payload()
        default_prediction = self.default.model_dump(mode="json")
        behavior = self.behavior.model_dump(mode="json")
        delay_prediction = self.delay.model_dump(mode="json")
        strategy = self.as_strategy_response().model_dump(mode="json")

        return {
            **self.as_invoice_list_item(),
            "payment_prediction": payment_prediction,
            "default_prediction": default_prediction,
            "risk_prediction": {
                "invoice_id": str(self.invoice["invoice_id"]),
                "risk_label": self.delay.risk_tier,
                "risk_score": int(self.delay.risk_score),
                "explanation": self.delay.explanation,
                "feature_drivers": delay_prediction.get("feature_drivers", []),
                "used_fallback": bool(self.delay.used_fallback),
                "llm_refined": bool(self.delay.llm_refined),
                "llm_used": bool(self.delay.llm_used),
                "prediction_source": str(self.delay.prediction_source),
                "model_version": str(self.delay.model_version),
            },
            "payment_behavior": behavior,
            "delay_prediction": delay_prediction,
            "strategy": strategy,
            "ai_recommendation": self._build_ai_recommendation(strategy),
            "shap_explanation": self._build_shap_explanation(delay_prediction),
            "model_inputs": {
                "payment": self.payment_request.model_dump(mode="json"),
                "behavior": self.behavior_request.model_dump(mode="json"),
            },
            "canonical_payload_version": "portfolio-intelligence-v1",
        }

    def _build_ai_recommendation(self, strategy: dict[str, Any]) -> dict[str, Any]:
        timeline_hours = int(strategy.get("next_action_in_hours") or 24)
        delay_pct = round(float(self.delay.delay_probability) * 100)
        _, _, pay_30 = self.cumulative_payment_probabilities()
        payment_pct = round(pay_30 * 100)
        default_pct = round(self.default_probability_value() * 100)
        return {
            "recommended_action": strategy["recommended_action"],
            "priority": strategy["urgency"],
            "timeline": f"Within {timeline_hours} Hours",
            "reasoning": (
                f"Predicted {delay_pct}% delay risk, {payment_pct}% chance of payment in 30 days, "
                f"and {default_pct}% default risk for a {self.behavior.behavior_type.lower()} profile."
            ),
            "additional_notes": (
                f"Portfolio rank #{strategy.get('priority_rank') or '—'} via the canonical pipeline. "
                f"Channel: {strategy.get('channel')}. "
                f"Automation eligible: {'Yes' if strategy.get('automation_flag') else 'No'}."
            ),
        }

    def _build_shap_explanation(self, delay_prediction: dict[str, Any]) -> dict[str, Any] | None:
        feature_drivers = delay_prediction.get("feature_drivers") or []
        top_features = []
        if feature_drivers:
            for driver in feature_drivers[:6]:
                contribution = float(driver.get("contribution") or 0.0)
                increases_risk = driver.get("direction") == "increases_prediction"
                top_features.append(
                    {
                        "feature_name": str(driver.get("display_name") or driver.get("feature_name")),
                        "feature_value": driver.get("feature_value"),
                        "shap_value": round(
                            abs(contribution) if increases_risk else -abs(contribution),
                            4,
                        ),
                        "impact": "negative" if increases_risk else "positive",
                    }
                )
        else:
            impact_weight = {"high": 0.24, "medium": 0.14, "low": 0.08}
            for driver in (delay_prediction.get("detailed_drivers") or [])[:6]:
                increases_risk = driver.get("direction") == "increases_risk"
                shap_value = impact_weight.get(str(driver.get("impact")).lower(), 0.1)
                top_features.append(
                    {
                        "feature_name": str(driver.get("driver") or "Risk driver"),
                        "feature_value": "",
                        "shap_value": round(shap_value if increases_risk else -shap_value, 4),
                        "impact": "negative" if increases_risk else "positive",
                    }
                )

        if not top_features:
            return None

        return {
            "top_features": top_features,
            "base_value": 0.5,
            "prediction_value": round(float(self.delay.delay_probability), 4),
        }


@dataclass
class PortfolioCustomerSnapshot:
    customer_id: str
    customer_name: str
    industry: str
    credit_score: int
    avg_days_to_pay: float
    payment_terms: int
    num_late_payments: int
    invoices: list[PortfolioInvoiceResult]

    def total_outstanding(self) -> float:
        return round(sum(float(item.invoice["amount"]) for item in self.invoices), 2)

    def total_overdue(self) -> float:
        return round(
            sum(
                float(item.invoice["amount"])
                for item in self.invoices
                if int(item.invoice["days_overdue"]) > 0
            ),
            2,
        )

    def overdue_invoice_count(self) -> int:
        return sum(1 for item in self.invoices if int(item.invoice["days_overdue"]) > 0)

    def weighted_delay_probability(self) -> float:
        total = self.total_outstanding()
        if total <= 0:
            return 0.0
        return round(
            sum(
                float(item.invoice["amount"]) * float(item.delay.delay_probability)
                for item in self.invoices
            ) / total,
            4,
        )

    def expected_recovery_rate(self) -> float:
        total = self.total_outstanding()
        if total <= 0:
            return 0.0
        return round(
            sum(
                float(item.invoice["amount"]) * float(item.payment.pay_30_days)
                for item in self.invoices
            ) / total,
            4,
        )

    def at_risk_amount(self) -> float:
        return round(
            sum(
                float(item.invoice["amount"])
                for item in self.invoices
                if float(item.delay.delay_probability) > 0.60
            ),
            2,
        )

    def primary_invoice_id(self) -> str | None:
        if not self.invoices:
            return None
        return str(self.invoices[0].invoice["invoice_id"])

    def concentration_pct(self, portfolio_total: float) -> float:
        if portfolio_total <= 0:
            return 0.0
        return round((self.total_outstanding() / portfolio_total) * 100.0, 1)


class PortfolioIntelligenceService:
    """Runs the predictive pipeline across the active invoice portfolio."""

    MAX_CONCURRENCY = 8

    def __init__(self) -> None:
        self.prediction_svc = PredictionService()
        self.behavior_svc = BehaviorService()
        self.delay_svc = DelayService()
        self.strategy_svc = StrategyService()

    def build_portfolio_results_sync(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[PortfolioInvoiceResult]:
        return self._run_sync(self.build_portfolio_results(rows))

    def build_customer_snapshots_sync(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[PortfolioCustomerSnapshot]:
        return self._run_sync(self.build_customer_snapshots(rows))

    def load_open_invoice_rows(self) -> list[dict[str, Any]]:
        try:
            with SessionLocal() as db:
                db_rows = db.execute(
                    text(
                        """
                        SELECT
                            i.invoice_number AS invoice_id,
                            i.invoice_number,
                            CAST(i.customer_id AS TEXT) AS customer_id,
                            c.name AS customer_name,
                            COALESCE(c.industry, 'unknown') AS industry,
                            COALESCE(i.outstanding_amount, i.amount) AS amount,
                            COALESCE(i.currency, 'INR') AS currency,
                            i.issue_date,
                            i.due_date,
                            i.status,
                            COALESCE(i.days_overdue, GREATEST((CURRENT_DATE - i.due_date), 0)) AS days_overdue,
                            COALESCE(c.credit_score, 650) AS credit_score,
                            COALESCE(c.avg_days_to_pay, c.payment_terms, 30) AS avg_days_to_pay,
                            COALESCE(c.num_late_payments, 0) AS num_late_payments,
                            COALESCE(c.num_invoices, 0) AS num_previous_invoices,
                            COALESCE(c.total_overdue, 0) AS customer_total_overdue,
                            COALESCE(i.payment_terms, c.payment_terms, 30) AS payment_terms,
                            COALESCE(i.nach_applicable, c.nach_mandate_active, FALSE) AS nach_applicable,
                            cb.historical_on_time_ratio,
                            cb.avg_delay_days AS behavior_avg_delay_days,
                            cb.repayment_consistency,
                            cb.partial_payment_frequency,
                            cb.prior_delayed_invoice_count,
                            cb.payment_after_followup_count,
                            cb.deterioration_trend,
                            cb.invoice_acknowledgement_behavior,
                            cb.transaction_success_failure_pattern
                        FROM invoices i
                        LEFT JOIN customers c ON c.id = i.customer_id
                        LEFT JOIN customer_behavior cb ON cb.customer_id = c.id
                        WHERE i.status IN ('open', 'overdue')
                        ORDER BY i.days_overdue DESC, i.due_date ASC
                        """
                    )
                ).mappings().all()
            rows = [self._normalize_row(dict(row)) for row in db_rows]
        except Exception as exc:
            logger.warning(
                "PortfolioIntelligenceService: DB unavailable (%s) — using JSON fallback",
                exc,
            )
            rows = [self._normalize_row(row) for row in load_invoices_from_json()]
        return [row for row in rows if row["status"] in ("open", "overdue")]

    async def build_portfolio_results(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[PortfolioInvoiceResult]:
        active_rows = rows if rows is not None else self.load_open_invoice_rows()
        if not active_rows:
            return []

        by_customer: dict[str, list[dict[str, Any]]] = {}
        for row in active_rows:
            by_customer.setdefault(str(row["customer_id"]), []).append(row)

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)
        tasks = [
            self._analyze_invoice(
                row=row,
                customer_rows=by_customer[str(row["customer_id"])],
                semaphore=semaphore,
            )
            for row in active_rows
        ]
        results = await asyncio.gather(*tasks)
        ranked = sorted(
            results,
            key=lambda item: (
                item.strategy.priority_score,
                item.delay.delay_probability,
                item.invoice["amount"],
            ),
            reverse=True,
        )
        for rank, result in enumerate(ranked, start=1):
            result.strategy.priority_rank = rank
        return ranked

    async def get_prioritized_worklist(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[PrioritizedInvoice]:
        results = await self.build_portfolio_results(rows)
        worklist = [result.as_prioritized_invoice() for result in results]
        worklist.sort(
            key=lambda item: (
                float(item.priority_score),
                float(item.delay_probability),
                float(item.amount),
            ),
            reverse=True,
        )
        for rank, item in enumerate(worklist, start=1):
            item.priority_rank = rank
        return worklist

    async def get_portfolio_strategies(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[StrategyResponse]:
        results = await self.build_portfolio_results(rows)
        return [result.as_strategy_response() for result in results]

    async def build_customer_snapshots(
        self,
        rows: list[dict[str, Any]] | None = None,
    ) -> list[PortfolioCustomerSnapshot]:
        results = await self.build_portfolio_results(rows)
        customer_map: dict[str, list[PortfolioInvoiceResult]] = {}
        for result in results:
            customer_map.setdefault(str(result.invoice["customer_id"]), []).append(result)

        snapshots = [
            PortfolioCustomerSnapshot(
                customer_id=customer_id,
                customer_name=str(items[0].invoice["customer_name"]),
                industry=str(items[0].invoice["industry"]),
                credit_score=int(items[0].invoice["credit_score"]),
                avg_days_to_pay=float(items[0].invoice["avg_days_to_pay"]),
                payment_terms=int(items[0].invoice["payment_terms"]),
                num_late_payments=int(items[0].invoice["num_late_payments"]),
                invoices=items,
            )
            for customer_id, items in customer_map.items()
        ]

        portfolio_total = sum(snapshot.total_outstanding() for snapshot in snapshots)
        return sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot.weighted_delay_probability(),
                snapshot.total_outstanding(),
                snapshot.overdue_invoice_count(),
                snapshot.concentration_pct(portfolio_total),
            ),
            reverse=True,
        )

    async def _analyze_invoice(
        self,
        *,
        row: dict[str, Any],
        customer_rows: list[dict[str, Any]],
        semaphore: asyncio.Semaphore,
    ) -> PortfolioInvoiceResult:
        async with semaphore:
            payment_request = self._build_payment_request(row, customer_rows)
            behavior_request = self._build_behavior_request(row, customer_rows)
            default_request = DefaultPredictionRequest(**payment_request.model_dump())

            payment_response, default_response, behavior_response = await asyncio.gather(
                self.prediction_svc.predict_payment(
                    payment_request,
                    allow_llm_refinement=False,
                ),
                self.prediction_svc.predict_default(
                    default_request,
                    allow_llm_refinement=False,
                ),
                self.behavior_svc.analyze(
                    behavior_request,
                    allow_llm_refinement=False,
                ),
            )

            delay_request = DelayPredictionRequest(
                invoice_id=payment_request.invoice_id,
                invoice_amount=payment_request.invoice_amount,
                days_overdue=payment_request.days_overdue,
                payment_terms=payment_request.payment_terms,
                customer_avg_invoice_amount=self._average_invoice_amount(customer_rows),
                industry=payment_request.industry,
                customer_credit_score=payment_request.customer_credit_score,
                customer_avg_days_to_pay=payment_request.customer_avg_days_to_pay,
                num_previous_invoices=payment_request.num_previous_invoices,
                num_late_payments=payment_request.num_late_payments,
                customer_total_overdue=payment_request.customer_total_overdue,
                behavior_type=behavior_response.behavior_type,
                on_time_ratio=behavior_response.on_time_ratio,
                avg_delay_days_historical=behavior_response.avg_delay_days,
                behavior_risk_score=behavior_response.behavior_risk_score,
                deterioration_trend=behavior_request.deterioration_trend,
                followup_dependency=behavior_response.followup_dependency,
            )
            delay_response = await self.delay_svc.predict(
                delay_request,
                allow_llm_refinement=False,
            )

            strategy_request = StrategyRequest(
                invoice_id=payment_request.invoice_id,
                customer_name=str(row["customer_name"]),
                invoice_amount=payment_request.invoice_amount,
                days_overdue=payment_request.days_overdue,
                delay_probability=delay_response.delay_probability,
                risk_tier=delay_response.risk_tier,
                recoverability_score=max(0.05, 1.0 - delay_response.delay_probability),
                nach_applicable=bool(
                    row.get("nach_applicable") or behavior_response.nach_recommended
                ),
                automation_feasible=delay_response.risk_tier != "High",
                behavior_type=behavior_response.behavior_type,
                followup_dependency=behavior_response.followup_dependency,
            )
            strategy_response = self.strategy_svc.optimize(strategy_request)

            return PortfolioInvoiceResult(
                invoice=row,
                payment_request=payment_request,
                behavior_request=behavior_request,
                payment=payment_response,
                default=default_response,
                behavior=behavior_response,
                delay=delay_response,
                strategy=strategy_response,
            )

    def _run_sync(self, coroutine):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        # Already inside an event loop — submit to the shared thread pool
        # to avoid spawning a new thread (and ThreadPoolExecutor) per call.
        return _SYNC_THREAD_POOL.submit(lambda: asyncio.run(coroutine)).result()

    def _normalize_row(self, raw: dict[str, Any]) -> dict[str, Any]:
        today = date.today()
        due_date = _to_date(raw.get("due_date"), today)
        issue_date = _to_date(raw.get("issue_date"), due_date)
        days_overdue = int(raw.get("days_overdue") or max((today - due_date).days, 0))
        payment_terms = int(raw.get("payment_terms") or max((due_date - issue_date).days, 30))
        amount = max(float(raw.get("amount") or 0.0), 0.0)
        avg_days_to_pay = float(raw.get("avg_days_to_pay") or 0.0)
        if avg_days_to_pay <= 0:
            avg_days_to_pay = float(payment_terms + (5 if raw.get("num_late_payments") else 0))

        return {
            "invoice_id": str(raw.get("invoice_id") or raw.get("invoice_number") or ""),
            "invoice_number": str(raw.get("invoice_number") or raw.get("invoice_id") or ""),
            "customer_id": str(raw.get("customer_id") or raw.get("invoice_id") or ""),
            "customer_name": str(raw.get("customer_name") or "Unknown Customer"),
            "industry": str(raw.get("industry") or "unknown"),
            "amount": amount,
            "currency": str(raw.get("currency") or "INR"),
            "issue_date": issue_date,
            "due_date": due_date,
            "status": str(raw.get("status") or ("overdue" if days_overdue > 0 else "open")),
            "days_overdue": days_overdue,
            "credit_score": int(raw.get("credit_score") or raw.get("customer_credit_score") or 650),
            "avg_days_to_pay": avg_days_to_pay,
            "num_late_payments": int(raw.get("num_late_payments") or 0),
            "num_previous_invoices": int(raw.get("num_previous_invoices") or 0),
            "customer_total_overdue": float(raw.get("customer_total_overdue") or 0.0),
            "payment_terms": payment_terms,
            "nach_applicable": bool(raw.get("nach_applicable", False)),
            "historical_on_time_ratio": raw.get("historical_on_time_ratio"),
            "behavior_avg_delay_days": raw.get("behavior_avg_delay_days"),
            "repayment_consistency": raw.get("repayment_consistency"),
            "partial_payment_frequency": raw.get("partial_payment_frequency"),
            "prior_delayed_invoice_count": raw.get("prior_delayed_invoice_count"),
            "payment_after_followup_count": raw.get("payment_after_followup_count"),
            "deterioration_trend": raw.get("deterioration_trend"),
            "invoice_acknowledgement_behavior": raw.get("invoice_acknowledgement_behavior"),
            "transaction_success_failure_pattern": raw.get("transaction_success_failure_pattern"),
        }

    def _build_payment_request(
        self,
        row: dict[str, Any],
        customer_rows: list[dict[str, Any]],
    ) -> PaymentPredictionRequest:
        num_previous_invoices = max(
            int(row.get("num_previous_invoices") or 0),
            len(customer_rows),
            int(row.get("num_late_payments") or 0) + 2,
            3,
        )
        customer_total_overdue = float(row.get("customer_total_overdue") or 0.0)
        if customer_total_overdue <= 0:
            customer_total_overdue = sum(
                float(item.get("amount") or 0.0)
                for item in customer_rows
                if str(item.get("status")) == "overdue"
            )

        return PaymentPredictionRequest(
            invoice_id=str(row["invoice_id"]),
            invoice_amount=max(float(row["amount"]), 1.0),
            days_overdue=max(int(row["days_overdue"]), 0),
            customer_credit_score=int(row["credit_score"]),
            customer_avg_days_to_pay=max(float(row["avg_days_to_pay"]), 1.0),
            payment_terms=max(int(row["payment_terms"]), 1),
            num_previous_invoices=num_previous_invoices,
            num_late_payments=max(int(row["num_late_payments"]), 0),
            industry=str(row["industry"]),
            customer_total_overdue=max(customer_total_overdue, 0.0),
        )

    def _build_behavior_request(
        self,
        row: dict[str, Any],
        customer_rows: list[dict[str, Any]],
    ) -> PaymentBehaviorRequest:
        total_invoices = max(
            int(row.get("num_previous_invoices") or 0),
            len(customer_rows),
            int(row.get("num_late_payments") or 0) + 2,
            3,
        )
        late_count = min(max(int(row.get("num_late_payments") or 0), 0), total_invoices)
        payment_terms = max(int(row.get("payment_terms") or 30), 1)
        avg_days_to_pay = max(float(row.get("avg_days_to_pay") or payment_terms), 0.0)
        overdue_customer_count = sum(
            1 for item in customer_rows if str(item.get("status")) == "overdue"
        )
        historical_gap = max(0.0, avg_days_to_pay - payment_terms)

        on_time_ratio = self._normalize_ratio(row.get("historical_on_time_ratio"))
        if on_time_ratio is None:
            on_time_ratio = _clamp(
                1.0
                - (late_count / max(total_invoices, 1)) * 0.85
                - min(historical_gap / max(payment_terms * 4.0, 1.0), 0.20),
                0.05,
                0.98,
            )

        avg_delay_days = row.get("behavior_avg_delay_days")
        if avg_delay_days is None:
            avg_delay_days = historical_gap if historical_gap > 0 else (
                min(max(float(row.get("days_overdue") or 0) * 0.35, 0.0), 45.0)
            )
        avg_delay_days = max(float(avg_delay_days), 0.0)

        repayment_consistency = row.get("repayment_consistency")
        if repayment_consistency is None:
            repayment_consistency = _clamp(
                0.92
                - (late_count / max(total_invoices, 1)) * 0.55
                - min(float(row.get("days_overdue") or 0) / 180.0, 0.20),
                0.15,
                0.95,
            )

        partial_payment_frequency = row.get("partial_payment_frequency")
        if partial_payment_frequency is None:
            partial_payment_frequency = _clamp(
                (0.06 if overdue_customer_count > 1 else 0.0)
                + min(late_count / max(total_invoices, 1) * 0.25, 0.25),
                0.0,
                0.75,
            )

        payment_after_followup_count = row.get("payment_after_followup_count")
        if payment_after_followup_count is None:
            payment_after_followup_count = min(
                total_invoices,
                max(overdue_customer_count, late_count),
            )

        deterioration_trend = row.get("deterioration_trend")
        if deterioration_trend is None:
            deterioration_trend = _clamp(
                (historical_gap / max(payment_terms, 1)) * 0.40
                + (late_count / max(total_invoices, 1)) * 0.25
                + (0.15 if float(row.get("days_overdue") or 0) >= 45 else 0.0),
                -1.0,
                1.0,
            )

        acknowledgement_behavior = row.get("invoice_acknowledgement_behavior")
        if not acknowledgement_behavior:
            if int(row.get("days_overdue") or 0) >= 60:
                acknowledgement_behavior = "ignored"
            elif int(row.get("days_overdue") or 0) >= 20:
                acknowledgement_behavior = "delayed"
            else:
                acknowledgement_behavior = "normal"

        txn_failure = row.get("transaction_success_failure_pattern")
        if txn_failure is None:
            txn_failure = _clamp(
                late_count / max(total_invoices, 1) * 0.15
                + (0.10 if int(row.get("days_overdue") or 0) >= 90 else 0.0),
                0.0,
                1.0,
            )

        return PaymentBehaviorRequest(
            customer_id=str(row["customer_id"]),
            customer_name=str(row["customer_name"]),
            historical_on_time_ratio=round(on_time_ratio, 4),
            avg_delay_days=round(avg_delay_days, 2),
            repayment_consistency=round(float(repayment_consistency), 4),
            partial_payment_frequency=round(float(partial_payment_frequency), 4),
            prior_delayed_invoice_count=late_count,
            payment_after_followup_count=int(payment_after_followup_count),
            total_invoices=total_invoices,
            deterioration_trend=round(float(deterioration_trend), 4),
            invoice_acknowledgement_behavior=str(acknowledgement_behavior),
            transaction_success_failure_pattern=round(float(txn_failure), 4),
        )

    def _average_invoice_amount(self, customer_rows: list[dict[str, Any]]) -> float:
        if not customer_rows:
            return 0.0
        total = sum(float(row.get("amount") or 0.0) for row in customer_rows)
        return round(total / max(len(customer_rows), 1), 2)

    def _normalize_ratio(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            return None
        if ratio > 1.0:
            ratio /= 100.0
        return _clamp(ratio, 0.0, 1.0)
