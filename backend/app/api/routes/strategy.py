"""
Collection Strategy Optimization API routes.

Endpoints:
  POST /optimize/collection-strategy  — compute optimised collection action + priority
  GET  /optimize/portfolio-strategy   — strategy for all open invoices with portfolio ranking
"""

import json
import logging
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.strategy import StrategyRequest, StrategyResponse
from app.services.risk_scoring import (
    build_amount_reference,
    delay_probability_from_score,
    risk_score,
    risk_tier_from_score,
)
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimize", tags=["Collection Strategy"])

strategy_svc = StrategyService()

from app.services.json_data import load_invoices_from_json


def _build_strategies(rows: list[dict]) -> list[StrategyResponse]:
    """Convert raw invoice rows into ranked StrategyResponse objects."""
    strategies: list[StrategyResponse] = []
    amount_reference = build_amount_reference(float(r["amount"] or 0) for r in rows)

    for row in rows:
        days_overdue = int(row["days_overdue"] or 0)
        amount = float(row["amount"] or 0)
        score = risk_score(days_overdue, amount, amount_reference)
        delay_prob = delay_probability_from_score(score)
        risk_tier = risk_tier_from_score(score)
        behavior_type = "Chronic Delayed Payer" if risk_tier == "High" else "Occasional Late Payer"
        nach = bool(row.get("nach_applicable")) or risk_tier == "High"

        req = StrategyRequest(
            invoice_id=str(row["invoice_id"]),
            customer_name=str(row.get("customer_name") or "Unknown Customer"),
            invoice_amount=max(float(amount), 1.0),
            days_overdue=days_overdue,
            delay_probability=delay_prob,
            risk_tier=risk_tier,
            nach_applicable=nach,
            behavior_type=behavior_type,
            followup_dependency=days_overdue >= 10,
        )
        result = strategy_svc.optimize(req)

        result.customer_name = req.customer_name
        result.amount = req.invoice_amount
        result.days_overdue = days_overdue
        result.risk_label = risk_tier
        result.risk_tier = risk_tier
        result.delay_probability = round(delay_prob, 4)
        result.behavior_type = behavior_type
        result.nach_recommended = nach

        strategies.append(result)

    return strategy_svc.rank_portfolio(strategies)


@router.post(
    "/collection-strategy",
    response_model=StrategyResponse,
    summary="Optimize collection strategy for an invoice",
    description=(
        "Takes delay risk, invoice signals, and behavior type to return a "
        "priority score, urgency, recommended action, and collection channel."
    ),
)
def optimize_strategy(request: StrategyRequest) -> StrategyResponse:
    return strategy_svc.optimize(request)


@router.get(
    "/portfolio-strategy",
    response_model=list[StrategyResponse],
    summary="Priority-ranked strategy for entire portfolio",
    description="Computes and ranks collection strategies for all open invoices in the portfolio.",
)
def get_portfolio_strategy() -> list[StrategyResponse]:
    # ── Try database first ────────────────────────────────────────────────────
    try:
        with SessionLocal() as db:
            db_rows = db.execute(
                text(
                    """
                    SELECT
                        i.invoice_number AS invoice_id,
                        c.name AS customer_name,
                        COALESCE(i.outstanding_amount, i.amount) AS amount,
                        i.days_overdue,
                        i.nach_applicable
                    FROM invoices i
                    LEFT JOIN customers c ON c.id = i.customer_id
                    WHERE i.status IN ('open', 'overdue')
                    ORDER BY i.days_overdue DESC, i.due_date ASC
                    """
                )
            ).mappings().all()
        rows = [dict(r) for r in db_rows]
        logger.info("portfolio-strategy: loaded %d rows from DB", len(rows))
    except Exception as exc:
        # ── Fallback: load from committed JSON data file ──────────────────────
        logger.warning("DB unavailable (%s) — falling back to invoices.json", exc)
        rows = load_invoices_from_json()
        logger.info("portfolio-strategy: loaded %d rows from JSON fallback", len(rows))

    return _build_strategies(rows)

