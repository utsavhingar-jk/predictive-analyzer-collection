#!/usr/bin/env python3
"""
Dashboard/API validation script.

Goals:
1. Verify that the main backend endpoints used by the UI are reachable.
2. Validate formula-level invariants for dashboard calculations.
3. Validate that backend ML-facing endpoints return safe, bounded outputs.

This script is API-only by design, so it can be run quickly without direct DB
access. For DB-vs-API reconciliation, use:
  python backend/scripts/validate_dashboard_data.py
"""

from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


API_BASE = "http://localhost:8000"

RISK_TIERS = {"High", "Medium", "Low"}
URGENCY_LEVELS = {"Critical", "High", "Medium", "Low"}
BEHAVIOR_TYPES = {
    "Consistent Payer",
    "Occasional Late Payer",
    "Reminder Driven Payer",
    "Partial Payment Payer",
    "Chronic Delayed Payer",
    "High Risk Defaulter",
}
BEHAVIOR_TRENDS = {"Improving", "Stable", "Worsening"}
PREDICTION_SOURCES = {"ml", "ml+llm", "rule-based"}
BORROWER_CONCENTRATION = {"Low", "Medium", "High"}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def request_json(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def add_check(results: list[CheckResult], name: str, ok: bool, detail: str) -> None:
    results.append(CheckResult(name=name, ok=ok, detail=detail))


def close_enough(a: float, b: float, eps: float = 0.05) -> bool:
    return abs(a - b) <= eps


def in_unit_interval(value: Any) -> bool:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return 0.0 <= num <= 1.0


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _format_money(value: Any) -> str:
    return f"${safe_float(value):,.2f}"


def validate_summary(results: list[CheckResult], summary: dict[str, Any]) -> None:
    total_invoices = safe_int(summary.get("total_invoices"))
    overdue_count = safe_int(summary.get("overdue_count"))
    total_outstanding = safe_float(summary.get("total_outstanding"))
    overdue_amount = safe_float(summary.get("overdue_amount"))
    amount_at_risk = safe_float(summary.get("amount_at_risk"))
    high_risk_count = safe_int(summary.get("high_risk_count"))
    risk_breakdown = summary.get("risk_breakdown") or {}
    breakdown_total = sum(safe_int(risk_breakdown.get(tier)) for tier in RISK_TIERS)

    add_check(
        results,
        "Summary.shape",
        isinstance(summary, dict),
        f"keys={sorted(summary.keys())}",
    )
    add_check(
        results,
        "Summary.non_negative_metrics",
        all(x >= 0 for x in (total_invoices, overdue_count, total_outstanding, overdue_amount, amount_at_risk, high_risk_count)),
        (
            f"total_invoices={total_invoices}, overdue_count={overdue_count}, "
            f"total_outstanding={total_outstanding:.2f}, overdue_amount={overdue_amount:.2f}, "
            f"amount_at_risk={amount_at_risk:.2f}, high_risk_count={high_risk_count}"
        ),
    )
    add_check(
        results,
        "Summary.overdue_count_lte_total",
        overdue_count <= total_invoices,
        f"overdue_count={overdue_count}, total_invoices={total_invoices}",
    )
    add_check(
        results,
        "Summary.overdue_amount_lte_total_outstanding",
        overdue_amount <= total_outstanding + 0.01,
        f"overdue_amount={overdue_amount:.2f}, total_outstanding={total_outstanding:.2f}",
    )
    add_check(
        results,
        "Summary.amount_at_risk_lte_total_outstanding",
        amount_at_risk <= total_outstanding + 0.01,
        f"amount_at_risk={amount_at_risk:.2f}, total_outstanding={total_outstanding:.2f}",
    )
    add_check(
        results,
        "Summary.risk_breakdown_sums_to_total",
        breakdown_total == total_invoices,
        f"breakdown_total={breakdown_total}, total_invoices={total_invoices}, risk_breakdown={risk_breakdown}",
    )
    add_check(
        results,
        "Summary.high_risk_count_matches_breakdown",
        high_risk_count == safe_int(risk_breakdown.get("High")),
        f"high_risk_count={high_risk_count}, breakdown_high={safe_int(risk_breakdown.get('High'))}",
    )


def validate_cashflow(results: list[CheckResult], cashflow: dict[str, Any], summary: dict[str, Any]) -> None:
    next_7 = safe_float(cashflow.get("next_7_days_inflow"))
    next_15 = safe_float(cashflow.get("next_15_days_inflow"))
    next_30 = safe_float(cashflow.get("next_30_days_inflow"))
    expected_7 = safe_float(cashflow.get("expected_7_day_collections"))
    expected_15 = safe_float(cashflow.get("expected_15_day_collections"))
    expected_30 = safe_float(cashflow.get("expected_30_day_collections"))
    amount_at_risk = safe_float(cashflow.get("amount_at_risk"))
    confidence = safe_float(cashflow.get("confidence"))
    overdue_carry_forward = safe_float(cashflow.get("overdue_carry_forward"))
    total_outstanding = safe_float(summary.get("total_outstanding"))
    shortfall_signal = bool(cashflow.get("shortfall_signal"))
    borrower_concentration = str(cashflow.get("borrower_concentration_risk"))
    daily_breakdown = cashflow.get("daily_breakdown") or []

    sum_30 = sum(safe_float(day.get("predicted_inflow")) for day in daily_breakdown)
    sum_7 = sum(safe_float(day.get("predicted_inflow")) for day in daily_breakdown[:7])
    sum_15 = sum(safe_float(day.get("predicted_inflow")) for day in daily_breakdown[:15])
    daily_dates = [str(day.get("date")) for day in daily_breakdown]

    add_check(
        results,
        "Cashflow.confidence_in_range",
        in_unit_interval(confidence),
        f"confidence={confidence}",
    )
    add_check(
        results,
        "Cashflow.expected_7_matches_next_7",
        close_enough(expected_7, next_7),
        f"expected_7={expected_7:.2f}, next_7={next_7:.2f}",
    )
    add_check(
        results,
        "Cashflow.expected_15_matches_next_15",
        close_enough(expected_15, next_15),
        f"expected_15={expected_15:.2f}, next_15={next_15:.2f}",
    )
    add_check(
        results,
        "Cashflow.expected_30_matches_next_30",
        close_enough(expected_30, next_30),
        f"expected_30={expected_30:.2f}, next_30={next_30:.2f}",
    )
    add_check(
        results,
        "Cashflow.next_7_lte_next_15",
        next_7 <= next_15 + 0.01,
        f"next_7={next_7:.2f}, next_15={next_15:.2f}",
    )
    add_check(
        results,
        "Cashflow.next_15_lte_next_30",
        next_15 <= next_30 + 0.01,
        f"next_15={next_15:.2f}, next_30={next_30:.2f}",
    )
    add_check(
        results,
        "Cashflow.next_7_lte_next_30",
        next_7 <= next_30 + 0.01,
        f"next_7={next_7:.2f}, next_30={next_30:.2f}",
    )
    add_check(
        results,
        "Cashflow.daily_breakdown_30_days",
        len(daily_breakdown) == 30,
        f"len(daily_breakdown)={len(daily_breakdown)}",
    )
    add_check(
        results,
        "Cashflow.daily_dates_unique",
        len(set(daily_dates)) == len(daily_dates),
        f"unique_dates={len(set(daily_dates))}, total_dates={len(daily_dates)}",
    )
    add_check(
        results,
        "Cashflow.daily_sum_matches_next_30",
        close_enough(sum_30, next_30, eps=2.0),
        f"sum_30={sum_30:.2f}, next_30={next_30:.2f}",
    )
    add_check(
        results,
        "Cashflow.first_7_sum_matches_next_7",
        close_enough(sum_7, next_7, eps=1.0),
        f"sum_7={sum_7:.2f}, next_7={next_7:.2f}",
    )
    add_check(
        results,
        "Cashflow.first_15_sum_matches_next_15",
        close_enough(sum_15, next_15, eps=1.5),
        f"sum_15={sum_15:.2f}, next_15={next_15:.2f}",
    )
    add_check(
        results,
        "Cashflow.amount_at_risk_lte_total_outstanding",
        amount_at_risk <= total_outstanding + 0.01,
        f"cashflow.amount_at_risk={amount_at_risk:.2f}, total_outstanding={total_outstanding:.2f}",
    )
    add_check(
        results,
        "Cashflow.overdue_carry_forward_non_negative",
        overdue_carry_forward >= 0.0,
        f"overdue_carry_forward={overdue_carry_forward:.2f}",
    )
    add_check(
        results,
        "Cashflow.borrower_concentration_valid",
        borrower_concentration in BORROWER_CONCENTRATION,
        f"borrower_concentration_risk={borrower_concentration}",
    )

    expected_shortfall = total_outstanding > 0 and (next_30 / total_outstanding) < 0.70
    add_check(
        results,
        "Cashflow.shortfall_formula_matches",
        shortfall_signal == expected_shortfall,
        (
            f"shortfall_signal={shortfall_signal}, expected={expected_shortfall}, "
            f"next_30={next_30:.2f}, total_outstanding={total_outstanding:.2f}"
        ),
    )


def validate_prioritized_worklist(results: list[CheckResult], worklist: list[dict[str, Any]]) -> None:
    add_check(
        results,
        "Prioritize.worklist_non_empty",
        len(worklist) > 0,
        f"items={len(worklist)}",
    )
    if not worklist:
        return

    invoice_ids = [str(item.get("invoice_id")) for item in worklist]
    scores = [safe_float(item.get("priority_score")) for item in worklist]

    add_check(
        results,
        "Prioritize.invoice_ids_unique",
        len(set(invoice_ids)) == len(invoice_ids),
        f"unique={len(set(invoice_ids))}, total={len(invoice_ids)}",
    )
    add_check(
        results,
        "Prioritize.sorted_by_priority_desc",
        all(scores[i] >= scores[i + 1] - 0.01 for i in range(len(scores) - 1)),
        f"top_scores={scores[:5]}",
    )

    for idx, item in enumerate(worklist[:10], start=1):
        amount = safe_float(item.get("amount"))
        delay_probability = safe_float(item.get("delay_probability"))
        priority_score = safe_float(item.get("priority_score"))
        risk_label = str(item.get("risk_label"))
        expected_priority = round(amount * delay_probability, 2)
        rounding_tolerance = max(0.11, amount * 0.00005 + 0.01)

        add_check(
            results,
            f"Prioritize.item_{idx}.delay_probability_in_range",
            in_unit_interval(delay_probability),
            f"invoice_id={item.get('invoice_id')}, delay_probability={delay_probability}",
        )
        add_check(
            results,
            f"Prioritize.item_{idx}.risk_label_valid",
            risk_label in RISK_TIERS,
            f"invoice_id={item.get('invoice_id')}, risk_label={risk_label}",
        )
        add_check(
            results,
            f"Prioritize.item_{idx}.priority_formula",
            close_enough(priority_score, expected_priority, eps=rounding_tolerance),
            (
                f"invoice_id={item.get('invoice_id')}, priority_score={priority_score:.2f}, "
                f"amount*delay_probability={expected_priority:.2f}, tolerance={rounding_tolerance:.3f}"
            ),
        )


def validate_portfolio_strategy(results: list[CheckResult], strategies: list[dict[str, Any]]) -> None:
    add_check(
        results,
        "PortfolioStrategy.non_empty",
        len(strategies) > 0,
        f"items={len(strategies)}",
    )
    if not strategies:
        return

    ranks = [safe_int(item.get("priority_rank")) for item in strategies]
    scores = [safe_int(item.get("priority_score")) for item in strategies]
    add_check(
        results,
        "PortfolioStrategy.rank_sequence",
        ranks == list(range(1, len(ranks) + 1)),
        f"first_ranks={ranks[:10]}",
    )
    add_check(
        results,
        "PortfolioStrategy.sorted_by_score_desc",
        all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)),
        f"top_scores={scores[:10]}",
    )

    for idx, item in enumerate(strategies[:10], start=1):
        urgency = str(item.get("urgency"))
        risk_tier = str(item.get("risk_tier") or item.get("risk_label"))
        delay_probability = safe_float(item.get("delay_probability"))
        priority_score = safe_int(item.get("priority_score"))
        candidate_actions = item.get("candidate_actions") or []
        selected_count = sum(1 for action in candidate_actions if action.get("is_selected"))

        add_check(
            results,
            f"PortfolioStrategy.item_{idx}.priority_score_range",
            0 <= priority_score <= 100,
            f"invoice_id={item.get('invoice_id')}, priority_score={priority_score}",
        )
        add_check(
            results,
            f"PortfolioStrategy.item_{idx}.delay_probability_in_range",
            in_unit_interval(delay_probability),
            f"invoice_id={item.get('invoice_id')}, delay_probability={delay_probability}",
        )
        add_check(
            results,
            f"PortfolioStrategy.item_{idx}.urgency_valid",
            urgency in URGENCY_LEVELS,
            f"invoice_id={item.get('invoice_id')}, urgency={urgency}",
        )
        add_check(
            results,
            f"PortfolioStrategy.item_{idx}.risk_tier_valid",
            risk_tier in RISK_TIERS,
            f"invoice_id={item.get('invoice_id')}, risk_tier={risk_tier}",
        )
        add_check(
            results,
            f"PortfolioStrategy.item_{idx}.single_selected_candidate",
            selected_count == 1 if candidate_actions else True,
            f"invoice_id={item.get('invoice_id')}, selected_count={selected_count}, candidate_actions={len(candidate_actions)}",
        )


def validate_borrower_portfolio(results: list[CheckResult], borrowers: list[dict[str, Any]]) -> None:
    add_check(
        results,
        "BorrowerPortfolio.non_empty",
        len(borrowers) > 0,
        f"items={len(borrowers)}",
    )
    if not borrowers:
        return

    scores = [safe_int(item.get("borrower_risk_score")) for item in borrowers]
    add_check(
        results,
        "BorrowerPortfolio.sorted_by_risk_score_desc",
        all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)),
        f"top_scores={scores[:10]}",
    )

    for idx, item in enumerate(borrowers[:10], start=1):
        customer_id = item.get("customer_id")
        tier = str(item.get("borrower_risk_tier"))
        risk_score = safe_int(item.get("borrower_risk_score"))
        weighted_delay_probability = safe_float(item.get("weighted_delay_probability"))
        expected_recovery_rate = safe_float(item.get("expected_recovery_rate"))
        total_outstanding = safe_float(item.get("total_outstanding"))
        at_risk_amount = safe_float(item.get("at_risk_amount"))

        add_check(
            results,
            f"BorrowerPortfolio.item_{idx}.risk_tier_valid",
            tier in RISK_TIERS,
            f"customer_id={customer_id}, tier={tier}",
        )
        add_check(
            results,
            f"BorrowerPortfolio.item_{idx}.risk_score_range",
            0 <= risk_score <= 100,
            f"customer_id={customer_id}, borrower_risk_score={risk_score}",
        )
        add_check(
            results,
            f"BorrowerPortfolio.item_{idx}.delay_probability_in_range",
            in_unit_interval(weighted_delay_probability),
            f"customer_id={customer_id}, weighted_delay_probability={weighted_delay_probability}",
        )
        add_check(
            results,
            f"BorrowerPortfolio.item_{idx}.recovery_rate_in_range",
            in_unit_interval(expected_recovery_rate),
            f"customer_id={customer_id}, expected_recovery_rate={expected_recovery_rate}",
        )
        add_check(
            results,
            f"BorrowerPortfolio.item_{idx}.at_risk_lte_total_outstanding",
            at_risk_amount <= total_outstanding + 0.01,
            f"customer_id={customer_id}, at_risk_amount={at_risk_amount:.2f}, total_outstanding={total_outstanding:.2f}",
        )


def validate_watchlist(results: list[CheckResult], watchlist: dict[str, Any]) -> None:
    customers = watchlist.get("customers") or []
    total_flagged = safe_int(watchlist.get("total_flagged"))
    critical_count = safe_int(watchlist.get("critical_count"))

    add_check(
        results,
        "Watchlist.total_flagged_matches_list",
        total_flagged == len(customers),
        f"total_flagged={total_flagged}, customers={len(customers)}",
    )
    add_check(
        results,
        "Watchlist.critical_lte_total",
        critical_count <= total_flagged,
        f"critical_count={critical_count}, total_flagged={total_flagged}",
    )


def build_prediction_payloads(invoice: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    invoice_id = str(invoice.get("invoice_id"))
    amount = max(1.0, safe_float(invoice.get("amount"), 1.0))
    days_overdue = max(0, safe_int(invoice.get("days_overdue")))
    credit_score = safe_int(invoice.get("credit_score"), 650)
    avg_days_to_pay = safe_float(invoice.get("avg_days_to_pay"), 30.0)
    payment_terms = max(1, safe_int(invoice.get("payment_terms"), 30))
    num_previous_invoices = max(1, safe_int(invoice.get("num_previous_invoices"), 10))
    num_late_payments = max(0, safe_int(invoice.get("num_late_payments")))
    industry = str(invoice.get("industry") or "unknown")
    customer_total_overdue = max(0.0, safe_float(invoice.get("customer_total_overdue")))

    prediction_payload = {
        "invoice_id": invoice_id,
        "invoice_amount": amount,
        "days_overdue": days_overdue,
        "customer_credit_score": credit_score,
        "customer_avg_days_to_pay": avg_days_to_pay,
        "payment_terms": payment_terms,
        "num_previous_invoices": num_previous_invoices,
        "num_late_payments": num_late_payments,
        "industry": industry,
        "customer_total_overdue": customer_total_overdue,
    }

    behavior = invoice.get("payment_behavior") or {}
    behavior_payload = {
        "customer_id": str(invoice.get("customer_id") or invoice.get("customer_name") or "sample-customer"),
        "customer_name": str(invoice.get("customer_name") or "Sample Customer"),
        "historical_on_time_ratio": safe_float(behavior.get("on_time_ratio"), 70.0) / 100.0,
        "avg_delay_days": max(0.0, safe_float(behavior.get("avg_delay_days"), max(4.0, days_overdue * 0.45))),
        "repayment_consistency": 0.6,
        "partial_payment_frequency": 0.1,
        "prior_delayed_invoice_count": num_late_payments,
        "payment_after_followup_count": num_late_payments,
        "total_invoices": num_previous_invoices,
        "deterioration_trend": 0.0,
        "invoice_acknowledgement_behavior": "normal",
        "transaction_success_failure_pattern": 0.05,
    }

    return prediction_payload, behavior_payload


def validate_invoice_detail(results: list[CheckResult], invoice_detail: dict[str, Any]) -> None:
    pay_7 = safe_float(invoice_detail.get("pay_7_days"))
    pay_15 = safe_float(invoice_detail.get("pay_15_days"))
    pay_30 = safe_float(invoice_detail.get("pay_30_days"))
    default_probability = safe_float(invoice_detail.get("default_probability"))
    risk_score = safe_int(invoice_detail.get("risk_score"))
    default_prediction = invoice_detail.get("default_prediction") or {}
    delay_prediction = invoice_detail.get("delay_prediction") or {}
    strategy = invoice_detail.get("strategy") or {}

    add_check(
        results,
        "InvoiceDetail.payment_probabilities_monotonic",
        0.0 <= pay_7 <= pay_15 <= pay_30 <= 1.0,
        f"pay_7={pay_7:.4f}, pay_15={pay_15:.4f}, pay_30={pay_30:.4f}",
    )
    add_check(
        results,
        "InvoiceDetail.risk_score_range",
        0 <= risk_score <= 100,
        f"invoice_id={invoice_detail.get('invoice_id')}, risk_score={risk_score}",
    )
    add_check(
        results,
        "InvoiceDetail.default_probability_in_range",
        in_unit_interval(default_probability),
        f"default_probability={default_probability:.4f}",
    )
    add_check(
        results,
        "InvoiceDetail.default_prediction_shape",
        (
            in_unit_interval(default_prediction.get("default_probability"))
            and str(default_prediction.get("default_risk_tier")) in RISK_TIERS
        ),
        f"default_prediction={default_prediction}",
    )
    add_check(
        results,
        "InvoiceDetail.delay_prediction_shape",
        in_unit_interval(delay_prediction.get("delay_probability")) and str(delay_prediction.get("risk_tier")) in RISK_TIERS,
        f"delay_prediction={delay_prediction}",
    )
    add_check(
        results,
        "InvoiceDetail.strategy_priority_range",
        0 <= safe_int(strategy.get("priority_score")) <= 100,
        f"strategy.priority_score={strategy.get('priority_score')}",
    )
    add_check(
        results,
        "InvoiceDetail.strategy_urgency_valid",
        str(strategy.get("urgency")) in URGENCY_LEVELS,
        f"strategy.urgency={strategy.get('urgency')}",
    )


def validate_payment_prediction(results: list[CheckResult], response: dict[str, Any]) -> None:
    p7 = safe_float(response.get("pay_7_days"))
    p15 = safe_float(response.get("pay_15_days"))
    p30 = safe_float(response.get("pay_30_days"))
    prediction_source = str(response.get("prediction_source"))
    llm_used = bool(response.get("llm_used"))
    used_fallback = bool(response.get("used_fallback"))
    explanation = str(response.get("explanation") or "").strip()

    add_check(
        results,
        "ML.Payment.probabilities_monotonic",
        0.0 <= p7 <= p15 <= p30 <= 1.0,
        f"pay_7={p7:.4f}, pay_15={p15:.4f}, pay_30={p30:.4f}",
    )
    add_check(
        results,
        "ML.Payment.prediction_source_valid",
        prediction_source in PREDICTION_SOURCES,
        f"prediction_source={prediction_source}",
    )
    add_check(
        results,
        "ML.Payment.llm_flag_consistent",
        (llm_used and prediction_source == "ml+llm") or (not llm_used and prediction_source != "ml+llm"),
        f"prediction_source={prediction_source}, llm_used={llm_used}",
    )
    add_check(
        results,
        "ML.Payment.fallback_flag_consistent",
        (used_fallback and prediction_source == "rule-based" and not llm_used) or (not used_fallback or prediction_source == "rule-based"),
        f"prediction_source={prediction_source}, used_fallback={used_fallback}, llm_used={llm_used}",
    )
    add_check(
        results,
        "ML.Payment.explanation_present",
        bool(explanation),
        f"explanation_len={len(explanation)}",
    )


def validate_default_prediction(results: list[CheckResult], response: dict[str, Any]) -> None:
    prediction_source = str(response.get("prediction_source"))
    llm_used = bool(response.get("llm_used"))
    used_fallback = bool(response.get("used_fallback"))
    default_probability = safe_float(response.get("default_probability"))
    confidence = safe_float(response.get("confidence"))
    default_risk_tier = str(response.get("default_risk_tier"))
    explanation = str(response.get("explanation") or "").strip()

    add_check(
        results,
        "ML.Default.probability_in_range",
        in_unit_interval(default_probability),
        f"default_probability={default_probability}",
    )
    add_check(
        results,
        "ML.Default.confidence_in_range",
        in_unit_interval(confidence),
        f"confidence={confidence}",
    )
    add_check(
        results,
        "ML.Default.risk_tier_valid",
        default_risk_tier in RISK_TIERS,
        f"default_risk_tier={default_risk_tier}",
    )
    add_check(
        results,
        "ML.Default.prediction_source_valid",
        prediction_source in {"ml", "rule-based"},
        f"prediction_source={prediction_source}",
    )
    add_check(
        results,
        "ML.Default.flags_consistent",
        (llm_used is False) and ((used_fallback and prediction_source == "rule-based") or (not used_fallback)),
        f"prediction_source={prediction_source}, used_fallback={used_fallback}, llm_used={llm_used}",
    )
    add_check(
        results,
        "ML.Default.explanation_present",
        bool(explanation),
        f"explanation_len={len(explanation)}",
    )


def validate_risk_prediction(results: list[CheckResult], response: dict[str, Any]) -> None:
    prediction_source = str(response.get("prediction_source"))
    llm_used = bool(response.get("llm_used"))
    used_fallback = bool(response.get("used_fallback"))
    risk_label = str(response.get("risk_label"))
    risk_score = safe_float(response.get("risk_score"))
    confidence = safe_float(response.get("confidence"))

    add_check(
        results,
        "ML.Risk.label_valid",
        risk_label in RISK_TIERS,
        f"risk_label={risk_label}",
    )
    add_check(
        results,
        "ML.Risk.score_in_range",
        in_unit_interval(risk_score),
        f"risk_score={risk_score}",
    )
    add_check(
        results,
        "ML.Risk.confidence_in_range",
        in_unit_interval(confidence),
        f"confidence={confidence}",
    )
    add_check(
        results,
        "ML.Risk.llm_flag_consistent",
        (llm_used and prediction_source == "ml+llm") or (not llm_used and prediction_source != "ml+llm"),
        f"prediction_source={prediction_source}, llm_used={llm_used}",
    )
    add_check(
        results,
        "ML.Risk.fallback_flag_consistent",
        (used_fallback and prediction_source == "rule-based" and not llm_used) or (not used_fallback or prediction_source == "rule-based"),
        f"prediction_source={prediction_source}, used_fallback={used_fallback}, llm_used={llm_used}",
    )


def validate_behavior_prediction(results: list[CheckResult], response: dict[str, Any]) -> None:
    prediction_source = str(response.get("prediction_source"))
    llm_used = bool(response.get("llm_used"))
    used_fallback = bool(response.get("used_fallback"))
    behavior_type = str(response.get("behavior_type"))
    trend = str(response.get("trend"))
    on_time_ratio = safe_float(response.get("on_time_ratio"))
    behavior_risk_score = safe_float(response.get("behavior_risk_score"))

    add_check(
        results,
        "ML.Behavior.type_valid",
        behavior_type in BEHAVIOR_TYPES,
        f"behavior_type={behavior_type}",
    )
    add_check(
        results,
        "ML.Behavior.trend_valid",
        trend in BEHAVIOR_TRENDS,
        f"trend={trend}",
    )
    add_check(
        results,
        "ML.Behavior.on_time_ratio_in_range",
        0.0 <= on_time_ratio <= 100.0,
        f"on_time_ratio={on_time_ratio}",
    )
    add_check(
        results,
        "ML.Behavior.risk_score_in_range",
        0.0 <= behavior_risk_score <= 100.0,
        f"behavior_risk_score={behavior_risk_score}",
    )
    add_check(
        results,
        "ML.Behavior.llm_flag_consistent",
        (llm_used and prediction_source == "ml+llm") or (not llm_used and prediction_source != "ml+llm"),
        f"prediction_source={prediction_source}, llm_used={llm_used}",
    )
    add_check(
        results,
        "ML.Behavior.fallback_flag_consistent",
        (used_fallback and prediction_source == "rule-based" and not llm_used) or (not used_fallback or prediction_source == "rule-based"),
        f"prediction_source={prediction_source}, used_fallback={used_fallback}, llm_used={llm_used}",
    )


def validate_delay_prediction(results: list[CheckResult], response: dict[str, Any], *, prefix: str = "ML.Delay") -> None:
    prediction_source = str(response.get("prediction_source"))
    llm_used = bool(response.get("llm_used"))
    used_fallback = bool(response.get("used_fallback"))
    delay_probability = safe_float(response.get("delay_probability"))
    risk_score = safe_int(response.get("risk_score"))
    risk_tier = str(response.get("risk_tier"))
    confidence = safe_float(response.get("confidence"))
    evidence_score = safe_float(response.get("evidence_score"))
    top_drivers = response.get("top_drivers") or []

    add_check(
        results,
        f"{prefix}.delay_probability_in_range",
        in_unit_interval(delay_probability),
        f"delay_probability={delay_probability}",
    )
    add_check(
        results,
        f"{prefix}.risk_score_range",
        0 <= risk_score <= 100,
        f"risk_score={risk_score}",
    )
    add_check(
        results,
        f"{prefix}.risk_tier_valid",
        risk_tier in RISK_TIERS,
        f"risk_tier={risk_tier}",
    )
    add_check(
        results,
        f"{prefix}.confidence_in_range",
        in_unit_interval(confidence),
        f"confidence={confidence}",
    )
    add_check(
        results,
        f"{prefix}.evidence_score_in_range",
        in_unit_interval(evidence_score),
        f"evidence_score={evidence_score}",
    )
    add_check(
        results,
        f"{prefix}.top_drivers_shape",
        isinstance(top_drivers, list),
        f"top_drivers_count={len(top_drivers)}",
    )
    add_check(
        results,
        f"{prefix}.llm_flag_consistent",
        (llm_used and prediction_source == "ml+llm") or (not llm_used and prediction_source != "ml+llm"),
        f"prediction_source={prediction_source}, llm_used={llm_used}",
    )
    add_check(
        results,
        f"{prefix}.fallback_flag_consistent",
        (used_fallback and prediction_source == "rule-based" and not llm_used) or (not used_fallback or prediction_source == "rule-based"),
        f"prediction_source={prediction_source}, used_fallback={used_fallback}, llm_used={llm_used}",
    )


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []

    summary = request_json("/invoices/summary")
    cashflow = request_json("/forecast/cashflow")
    prioritized_worklist = request_json("/prioritize/invoices")
    portfolio_strategy = request_json("/optimize/portfolio-strategy")
    watchlist = request_json("/sentinel/watchlist")
    invoice_list = request_json("/invoices/?limit=5")
    borrower_portfolio = request_json("/predict/borrowers/portfolio")

    add_check(results, "Endpoint.InvoiceSummary", isinstance(summary, dict), f"type={type(summary).__name__}")
    add_check(results, "Endpoint.CashflowForecast", isinstance(cashflow, dict), f"type={type(cashflow).__name__}")
    add_check(results, "Endpoint.PrioritizedWorklist", isinstance(prioritized_worklist, list), f"type={type(prioritized_worklist).__name__}")
    add_check(results, "Endpoint.PortfolioStrategy", isinstance(portfolio_strategy, list), f"type={type(portfolio_strategy).__name__}")
    add_check(results, "Endpoint.SentinelWatchlist", isinstance(watchlist, dict), f"type={type(watchlist).__name__}")
    add_check(results, "Endpoint.InvoiceList", isinstance(invoice_list, dict), f"type={type(invoice_list).__name__}")
    add_check(results, "Endpoint.BorrowerPortfolio", isinstance(borrower_portfolio, list), f"type={type(borrower_portfolio).__name__}")

    validate_summary(results, summary)
    validate_cashflow(results, cashflow, summary)
    validate_prioritized_worklist(results, prioritized_worklist if isinstance(prioritized_worklist, list) else [])
    validate_portfolio_strategy(results, portfolio_strategy if isinstance(portfolio_strategy, list) else [])
    validate_watchlist(results, watchlist)
    validate_borrower_portfolio(results, borrower_portfolio if isinstance(borrower_portfolio, list) else [])

    invoices = invoice_list.get("invoices") or []
    add_check(results, "Invoices.sample_exists", len(invoices) > 0, f"invoices_returned={len(invoices)}")
    if not invoices:
        return results

    sample_invoice_id = str(invoices[0].get("invoice_id"))
    invoice_detail = request_json(f"/invoices/{sample_invoice_id}")
    add_check(
        results,
        "InvoiceDetail.resolves",
        str(invoice_detail.get("invoice_id")) == sample_invoice_id,
        f"requested={sample_invoice_id}, returned={invoice_detail.get('invoice_id')}",
    )
    validate_invoice_detail(results, invoice_detail)

    prediction_payload, behavior_payload = build_prediction_payloads(invoice_detail)

    payment_prediction = request_json("/predict/payment", method="POST", payload=prediction_payload)
    default_prediction = request_json("/predict/default", method="POST", payload=prediction_payload)
    risk_prediction = request_json("/predict/risk", method="POST", payload=prediction_payload)
    behavior_prediction = request_json("/analyze/payment-behavior", method="POST", payload=behavior_payload)

    delay_payload = {
        "invoice_id": prediction_payload["invoice_id"],
        "invoice_amount": prediction_payload["invoice_amount"],
        "days_overdue": prediction_payload["days_overdue"],
        "payment_terms": prediction_payload["payment_terms"],
        "customer_avg_invoice_amount": prediction_payload["invoice_amount"],
        "customer_credit_score": prediction_payload["customer_credit_score"],
        "customer_avg_days_to_pay": prediction_payload["customer_avg_days_to_pay"],
        "num_previous_invoices": prediction_payload["num_previous_invoices"],
        "num_late_payments": prediction_payload["num_late_payments"],
        "industry": prediction_payload["industry"],
        "customer_total_overdue": prediction_payload["customer_total_overdue"],
        "behavior_type": behavior_prediction.get("behavior_type"),
        "on_time_ratio": behavior_prediction.get("on_time_ratio"),
        "avg_delay_days_historical": behavior_prediction.get("avg_delay_days"),
        "behavior_risk_score": behavior_prediction.get("behavior_risk_score"),
        "deterioration_trend": (
            0.3 if behavior_prediction.get("trend") == "Worsening"
            else -0.2 if behavior_prediction.get("trend") == "Improving"
            else 0.0
        ),
        "followup_dependency": behavior_prediction.get("followup_dependency"),
    }
    delay_prediction = request_json("/predict/delay", method="POST", payload=delay_payload)

    validate_payment_prediction(results, payment_prediction)
    validate_default_prediction(results, default_prediction)
    validate_risk_prediction(results, risk_prediction)
    validate_behavior_prediction(results, behavior_prediction)
    validate_delay_prediction(results, delay_prediction)

    # Explicit test for canonical behavior enum support in the backend.
    ignored_behavior_payload = dict(behavior_payload)
    ignored_behavior_payload["invoice_acknowledgement_behavior"] = "ignored"
    ignored_behavior_prediction = request_json(
        "/analyze/payment-behavior",
        method="POST",
        payload=ignored_behavior_payload,
    )
    add_check(
        results,
        "ML.Behavior.ignored_ack_payload_accepted",
        str(ignored_behavior_prediction.get("behavior_type")) in BEHAVIOR_TYPES,
        f"behavior_type={ignored_behavior_prediction.get('behavior_type')}",
    )

    # Explicit test for high CIBIL range support (up to 900).
    high_credit_delay_payload = dict(delay_payload)
    high_credit_delay_payload.update(
        {
            "invoice_id": "probe-high-credit",
            "customer_credit_score": 897,
            "invoice_amount": 100000.0,
            "customer_avg_invoice_amount": 100000.0,
            "customer_total_overdue": 0.0,
            "days_overdue": 0,
            "num_late_payments": 1,
            "num_previous_invoices": 12,
            "industry": "technology",
        }
    )
    high_credit_delay_prediction = request_json(
        "/predict/delay",
        method="POST",
        payload=high_credit_delay_payload,
    )
    validate_delay_prediction(results, high_credit_delay_prediction, prefix="ML.Delay.HighCredit")

    # Explicit fallback path test: sparse evidence + weaker profile should trigger rule engine.
    fallback_delay_payload = {
        "invoice_id": "probe-fallback",
        "invoice_amount": 300000.0,
        "days_overdue": 0,
        "payment_terms": 45,
        "customer_avg_invoice_amount": 290000.0,
        "customer_credit_score": 540,
        "customer_avg_days_to_pay": 52.0,
        "num_previous_invoices": 2,
        "num_late_payments": 1,
        "industry": "real estate",
        "customer_total_overdue": 180000.0,
    }
    fallback_delay_prediction = request_json(
        "/predict/delay",
        method="POST",
        payload=fallback_delay_payload,
    )
    validate_delay_prediction(results, fallback_delay_prediction, prefix="ML.Delay.Fallback")
    add_check(
        results,
        "ML.Delay.Fallback.rule_path_triggered",
        (
            fallback_delay_prediction.get("prediction_source") == "rule-based"
            and bool(fallback_delay_prediction.get("used_fallback")) is True
            and bool(fallback_delay_prediction.get("llm_used")) is False
        ),
        (
            f"prediction_source={fallback_delay_prediction.get('prediction_source')}, "
            f"used_fallback={fallback_delay_prediction.get('used_fallback')}, "
            f"llm_used={fallback_delay_prediction.get('llm_used')}"
        ),
    )

    return results


def main() -> int:
    try:
        checks = run_checks()
    except urllib.error.URLError as exc:
        print(f"ERROR: Could not reach backend API at {API_BASE}: {exc}")
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    print("=" * 90)
    print("DASHBOARD + BACKEND ML VALIDATION")
    print("=" * 90)

    passed = 0
    failed = 0
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        if check.ok:
            passed += 1
        else:
            failed += 1

    print("-" * 90)
    print(f"Result: {passed} passed, {failed} failed, total {len(checks)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
