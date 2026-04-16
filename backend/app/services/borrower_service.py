"""
Borrower-Level Prediction Service.

Aggregates all open invoices for a borrower and computes:
  - Weighted delay probability (amount-weighted across invoices)
  - Borrower risk score and tier
  - Expected recovery amount and rate
  - Amount at risk (delay_prob > 0.60)
  - Borrower DSO vs portfolio average
  - Escalation and NACH recommendation
  - Relationship-level action recommendation
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.schemas.borrower import (
    BorrowerInvoiceSummary,
    BorrowerPortfolioItem,
    BorrowerPredictionRequest,
    BorrowerPredictionResponse,
)
from app.services.llm_refiner import LLMRefiner
from app.services.json_data import load_invoices_from_json

logger = logging.getLogger(__name__)
settings = get_settings()

# Portfolio-level benchmark DSO (days)
PORTFOLIO_BENCHMARK_DSO = 45.0
# Shortfall threshold for recovery confidence
HIGH_RECOVERY_THRESHOLD = 0.70
MEDIUM_RECOVERY_THRESHOLD = 0.40


class BorrowerService:
    def __init__(self) -> None:
        self.ml_base = settings.ML_SERVICE_URL
        self.timeout = 10.0
        self.refiner = LLMRefiner()
        # Shared client: thread-safe for concurrent POSTs; avoids new TCP pool per borrower
        self._http = httpx.Client(timeout=self.timeout)

    def predict_borrower(
        self,
        request: BorrowerPredictionRequest,
        portfolio_total: float = 0.0,
        *,
        refine_with_llm: bool = True,
    ) -> BorrowerPredictionResponse:
        """
        3-phase borrower pipeline:
          1) ML service prediction
          2) GPT refinement using ML input/output (optional; never for GET /borrowers/portfolio)
          3) Rule-based fallback (this service logic)

        If invoices are not passed in the request, they are looked up
        from database invoices.
        """
        invoices = request.invoices

        # Auto-populate from DB if not supplied
        if not invoices:
            invoices = self._load_borrower_invoices(request.customer_id)

        if not invoices:
            return self._empty_borrower_response(request)

        ml_payload = self._build_ml_payload(request, invoices, portfolio_total)
        try:
            resp = self._http.post(
                f"{self.ml_base}/predict/borrower",
                json=ml_payload,
            )
            resp.raise_for_status()
            ml_result = BorrowerPredictionResponse(**resp.json())
            ml_result.prediction_source = "ml"
            ml_result.llm_refined = False
            ml_result.used_fallback = False
            ml_result.explanation = ml_result.explanation or (
                f"Phase 1 ML output ({ml_result.model_version}) generated from borrower exposure and invoice-level features."
            )

            if refine_with_llm:
                refined = self.refiner.refine_borrower_sync(
                    {
                        "model_input": ml_payload,
                        "ml_output": ml_result.model_dump(),
                    }
                )
                if refined:
                    ml_result.borrower_risk_score = refined["borrower_risk_score"]
                    ml_result.borrower_risk_tier = refined["borrower_risk_tier"]
                    ml_result.weighted_delay_probability = refined["weighted_delay_probability"]
                    ml_result.expected_recovery_rate = refined["expected_recovery_rate"]
                    ml_result.escalation_recommended = refined["escalation_recommended"]
                    ml_result.relationship_action = refined["relationship_action"]
                    ml_result.borrower_summary = refined["borrower_summary"]
                    ml_result.model_version = f"{ml_result.model_version}+gpt-refiner-v1"
                    ml_result.prediction_source = "ml+llm"
                    ml_result.llm_refined = True
                    ml_result.used_fallback = False
                    ml_result.explanation = refined["explanation"]
            return ml_result
        except Exception as exc:
            logger.warning("Borrower ML pipeline failed (%s) — using rule-based fallback", exc)
            return self._rule_based_predict_borrower(request, invoices, portfolio_total)

    def _build_ml_payload(
        self,
        request: BorrowerPredictionRequest,
        invoices: list[BorrowerInvoiceSummary],
        portfolio_total: float,
    ) -> dict:
        return {
            "customer_id": str(request.customer_id),
            "customer_name": request.customer_name,
            "industry": request.industry,
            "credit_score": int(request.credit_score),
            "avg_days_to_pay": float(request.avg_days_to_pay),
            "payment_terms": int(request.payment_terms),
            "num_late_payments": int(request.num_late_payments),
            "portfolio_total_outstanding": float(max(portfolio_total, 0.0)),
            "invoices": [inv.model_dump() for inv in invoices],
        }

    def _rule_response_to_portfolio_item(self, rule: BorrowerPredictionResponse) -> BorrowerPortfolioItem:
        """Map backend rule-only prediction to portfolio table row."""
        return BorrowerPortfolioItem(
            customer_id=rule.customer_id,
            customer_name=rule.customer_name,
            industry=rule.industry,
            total_outstanding=rule.total_outstanding,
            overdue_invoice_count=rule.overdue_invoice_count,
            borrower_risk_tier=rule.borrower_risk_tier,
            borrower_risk_score=rule.borrower_risk_score,
            weighted_delay_probability=rule.weighted_delay_probability,
            expected_recovery_rate=rule.expected_recovery_rate,
            at_risk_amount=rule.at_risk_amount,
            escalation_recommended=rule.escalation_recommended,
            relationship_action=rule.relationship_action,
            concentration_pct=rule.concentration_pct,
        )

    def _merge_hybrid_ml_and_rules(
        self,
        ml: dict,
        rule: BorrowerPredictionResponse,
        w_ml: float,
    ) -> BorrowerPortfolioItem:
        """
        Combine ML-service output with backend rule engine (same invoice aggregates).

        ``w_ml`` in [0, 1]: weight on ML vs rules for scores and probabilities.
        Exposure uses DB-backed rule totals; ``relationship_action`` is from rules (policy).
        Escalation is true if either ML or rules recommends it.
        """
        w_ml = max(0.0, min(1.0, w_ml))
        w_r = 1.0 - w_ml

        ml_score = int(ml.get("borrower_risk_score", rule.borrower_risk_score))
        score = int(round(w_ml * ml_score + w_r * rule.borrower_risk_score))
        score = max(0, min(100, score))
        tier = "High" if score >= 65 else "Medium" if score >= 35 else "Low"

        wdp = w_ml * float(ml["weighted_delay_probability"]) + w_r * rule.weighted_delay_probability
        wdp = round(max(0.0, min(1.0, wdp)), 4)

        err = w_ml * float(ml["expected_recovery_rate"]) + w_r * rule.expected_recovery_rate
        err = round(max(0.0, min(1.0, err)), 4)

        at_risk = max(float(ml["at_risk_amount"]), float(rule.at_risk_amount))

        escalate = bool(ml.get("escalation_recommended")) or rule.escalation_recommended

        conc = w_ml * float(ml.get("concentration_pct", rule.concentration_pct)) + w_r * rule.concentration_pct
        conc = round(conc, 1)

        return BorrowerPortfolioItem(
            customer_id=str(rule.customer_id),
            customer_name=rule.customer_name,
            industry=rule.industry,
            total_outstanding=float(rule.total_outstanding),
            overdue_invoice_count=int(rule.overdue_invoice_count),
            borrower_risk_tier=tier,
            borrower_risk_score=score,
            weighted_delay_probability=wdp,
            expected_recovery_rate=err,
            at_risk_amount=round(at_risk, 2),
            escalation_recommended=escalate,
            relationship_action=rule.relationship_action,
            concentration_pct=conc,
        )

    def _rule_based_predict_borrower(
        self,
        request: BorrowerPredictionRequest,
        invoices: list[BorrowerInvoiceSummary],
        portfolio_total: float = 0.0,
    ) -> BorrowerPredictionResponse:
        # ── Aggregate exposure ────────────────────────────────────────────────
        total_outstanding = sum(inv.amount for inv in invoices)
        total_overdue = sum(inv.amount for inv in invoices if inv.status == "overdue")
        open_count = len(invoices)
        overdue_count = sum(1 for inv in invoices if inv.status == "overdue")

        # ── Weighted delay probability (weight = invoice amount) ──────────────
        if total_outstanding > 0:
            weighted_delay_prob = sum(
                inv.delay_probability * inv.amount for inv in invoices
            ) / total_outstanding
        else:
            weighted_delay_prob = 0.0
        weighted_delay_prob = round(weighted_delay_prob, 4)

        # ── Expected recovery ─────────────────────────────────────────────────
        expected_recovery = sum(inv.amount * inv.pay_30_days for inv in invoices)
        recovery_rate = (expected_recovery / total_outstanding) if total_outstanding > 0 else 0.0
        at_risk_amount = sum(
            inv.amount for inv in invoices if inv.delay_probability > 0.60
        )

        recovery_confidence = (
            "High" if recovery_rate >= HIGH_RECOVERY_THRESHOLD
            else "Medium" if recovery_rate >= MEDIUM_RECOVERY_THRESHOLD
            else "Low"
        )

        # ── Borrower risk score (0–100) ───────────────────────────────────────
        overdue_ratio = total_overdue / total_outstanding if total_outstanding > 0 else 0.0
        credit_factor = max(0.0, (700 - request.credit_score) / 400)
        late_factor = min(1.0, request.num_late_payments / 10)
        concentration_pct_raw = (total_outstanding / portfolio_total) if portfolio_total > 0 else 0.0
        concentration_factor = min(1.0, concentration_pct_raw / 0.5)

        raw_score = (
            weighted_delay_prob * 0.40
            + overdue_ratio * 0.20
            + credit_factor * 0.20
            + late_factor * 0.10
            + concentration_factor * 0.10
        )
        borrower_risk_score = int(min(100, round(raw_score * 100)))

        if borrower_risk_score >= 65:
            borrower_risk_tier = "High"
        elif borrower_risk_score >= 35:
            borrower_risk_tier = "Medium"
        else:
            borrower_risk_tier = "Low"

        borrower_dso = request.avg_days_to_pay
        if borrower_dso < PORTFOLIO_BENCHMARK_DSO * 0.85:
            dso_vs_portfolio = "Better"
        elif borrower_dso > PORTFOLIO_BENCHMARK_DSO * 1.15:
            dso_vs_portfolio = "Worse"
        else:
            dso_vs_portfolio = "On Par"

        nach_recommended = borrower_risk_tier == "High" and request.num_late_payments >= 3

        escalation_recommended = (
            borrower_risk_tier == "High" and total_outstanding > 50_000
        ) or (weighted_delay_prob > 0.75) or (overdue_count >= 2 and total_overdue > 30_000)

        relationship_action = self._relationship_action(
            borrower_risk_tier, total_outstanding, overdue_count,
            weighted_delay_prob, nach_recommended
        )

        concentration_pct = round(concentration_pct_raw * 100, 1)

        summary = self._build_summary(
            request, borrower_risk_tier, borrower_risk_score,
            weighted_delay_prob, expected_recovery, recovery_rate,
            total_outstanding, overdue_count, escalation_recommended,
        )

        return BorrowerPredictionResponse(
            customer_id=str(request.customer_id),
            customer_name=request.customer_name,
            industry=request.industry,
            total_outstanding=round(total_outstanding, 2),
            total_overdue=round(total_overdue, 2),
            open_invoice_count=open_count,
            overdue_invoice_count=overdue_count,
            concentration_pct=concentration_pct,
            weighted_delay_probability=weighted_delay_prob,
            borrower_risk_score=borrower_risk_score,
            borrower_risk_tier=borrower_risk_tier,
            expected_recovery_amount=round(expected_recovery, 2),
            expected_recovery_rate=round(recovery_rate, 4),
            at_risk_amount=round(at_risk_amount, 2),
            recovery_confidence=recovery_confidence,
            borrower_dso=borrower_dso,
            dso_vs_portfolio=dso_vs_portfolio,
            escalation_recommended=escalation_recommended,
            nach_recommended=nach_recommended,
            relationship_action=relationship_action,
            invoices=invoices,
            borrower_summary=summary,
            model_version="borrower-rule-v1",
            prediction_source="rule-based",
            llm_refined=False,
            used_fallback=True,
            explanation="Phase 3 fallback: rule-based borrower aggregation using weighted delay, overdue ratio, concentration, and credit stress.",
        )

    def get_portfolio_borrowers(self) -> list[BorrowerPortfolioItem]:
        """
        Build a ranked list of all borrowers in the portfolio.
        Uses database-backed invoices.

        Each row blends **ML service** output with the **backend rule engine** using
        ``BORROWER_PORTFOLIO_HYBRID_ML_WEIGHT`` (default 0.5). OpenAI is not used.

        Primary path: one POST to ml-service ``/predict/borrowers/portfolio``.
        Fallback: parallel per-borrower POST to ``/predict/borrower`` if batch fails.
        """
        customer_map, portfolio_total = self._load_portfolio_customer_map()
        if not customer_map:
            return []

        w_hybrid = settings.BORROWER_PORTFOLIO_HYBRID_ML_WEIGHT

        borrowers_payload: list[dict] = []
        for data in customer_map.values():
            req = BorrowerPredictionRequest(
                customer_id=data["customer_id"],
                customer_name=data["customer_name"],
                industry=data["industry"],
                credit_score=data["credit_score"],
                avg_days_to_pay=data["avg_days_to_pay"],
                payment_terms=data["payment_terms"],
                num_late_payments=data["num_late_payments"],
                invoices=data["invoices"],
            )
            borrowers_payload.append(
                self._build_ml_payload(req, data["invoices"], portfolio_total)
            )

        try:
            resp = self._http.post(
                f"{self.ml_base}/predict/borrowers/portfolio",
                json={
                    "portfolio_total_outstanding": portfolio_total,
                    "borrowers": borrowers_payload,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            ml_rows = resp.json()
            ordered = list(customer_map.values())
            results: list[BorrowerPortfolioItem] = []
            for ml_row, data in zip(ml_rows, ordered):
                req = BorrowerPredictionRequest(
                    customer_id=data["customer_id"],
                    customer_name=data["customer_name"],
                    industry=data["industry"],
                    credit_score=data["credit_score"],
                    avg_days_to_pay=data["avg_days_to_pay"],
                    payment_terms=data["payment_terms"],
                    num_late_payments=data["num_late_payments"],
                    invoices=data["invoices"],
                )
                rule = self._rule_based_predict_borrower(req, data["invoices"], portfolio_total)
                results.append(self._merge_hybrid_ml_and_rules(ml_row, rule, w_hybrid))
            return sorted(results, key=lambda b: b.borrower_risk_score, reverse=True)
        except Exception as exc:
            logger.warning(
                "ML batch portfolio failed (%s) — falling back to parallel /predict/borrower",
                exc,
            )

        max_workers = max(1, min(settings.BORROWER_PORTFOLIO_MAX_WORKERS, len(customer_map)))

        def _predict_one(data: dict) -> BorrowerPortfolioItem:
            req = BorrowerPredictionRequest(
                customer_id=data["customer_id"],
                customer_name=data["customer_name"],
                industry=data["industry"],
                credit_score=data["credit_score"],
                avg_days_to_pay=data["avg_days_to_pay"],
                payment_terms=data["payment_terms"],
                num_late_payments=data["num_late_payments"],
                invoices=data["invoices"],
            )
            rule = self._rule_based_predict_borrower(req, data["invoices"], portfolio_total)
            pred = self.predict_borrower(
                req,
                portfolio_total=portfolio_total,
                refine_with_llm=False,
            )
            if pred.prediction_source in ("ml", "ml+llm"):
                return self._merge_hybrid_ml_and_rules(pred.model_dump(), rule, w_hybrid)
            return self._rule_response_to_portfolio_item(rule)

        rows = list(customer_map.values())
        if max_workers == 1 or len(rows) == 1:
            results = [_predict_one(d) for d in rows]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(_predict_one, rows))

        return sorted(results, key=lambda b: b.borrower_risk_score, reverse=True)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_borrower_invoices(self, customer_id: str) -> list[BorrowerInvoiceSummary]:
        """Look up open invoices for a customer from database."""
        try:
            with SessionLocal() as db:
                rows = db.execute(
                    text(
                        """
                        SELECT
                            i.invoice_number AS invoice_id,
                            COALESCE(i.outstanding_amount, i.amount) AS amount,
                            i.days_overdue,
                            i.status
                        FROM invoices i
                        WHERE CAST(i.customer_id AS TEXT) = :customer_id
                          AND i.status IN ('open', 'overdue')
                        ORDER BY i.days_overdue DESC, i.due_date ASC
                        """
                    ),
                    {"customer_id": str(customer_id)},
                ).mappings().all()
            if rows:
                result: list[BorrowerInvoiceSummary] = []
                for row in rows:
                    days_overdue = int(row["days_overdue"] or 0)
                    delay_prob = round(min(0.95, max(0.05, days_overdue / 45.0)), 4)
                    pay_30 = round(1.0 - delay_prob, 4)
                    risk_label = "High" if days_overdue >= 30 else "Medium" if days_overdue >= 10 else "Low"
                    result.append(
                        BorrowerInvoiceSummary(
                            invoice_id=str(row["invoice_id"]),
                            amount=float(row["amount"] or 0),
                            days_overdue=days_overdue,
                            status=str(row["status"]),
                            risk_label=risk_label,
                            delay_probability=delay_prob,
                            pay_30_days=pay_30,
                            recommended_action=self._recommended_action_for_days_overdue(days_overdue),
                        )
                    )
                return result
        except Exception:
            logger.warning("Failed loading borrower invoices from DB, using fallback")
            raw = load_invoices_from_json()
            rows = [r for r in raw if str(r.get("customer_id") or r.get("invoice_id")) == str(customer_id)]
            result = []
            for row in rows:
                days_overdue = int(row.get("days_overdue", 0))
                delay_prob = round(min(0.95, max(0.05, days_overdue / 45.0)), 4)
                pay_30 = round(1.0 - delay_prob, 4)
                risk_label = "High" if days_overdue >= 30 else "Medium" if days_overdue >= 10 else "Low"
                result.append(
                    BorrowerInvoiceSummary(
                        invoice_id=str(row["invoice_id"]),
                        amount=float(row.get("amount", 0)),
                        days_overdue=days_overdue,
                        status=str(row.get("status", "open")),
                        risk_label=risk_label,
                        delay_probability=delay_prob,
                        pay_30_days=pay_30,
                        recommended_action=self._recommended_action_for_days_overdue(days_overdue),
                    )
                )
            return result

    def _load_portfolio_customer_map(self) -> tuple[dict[str, dict], float]:
        """Load grouped borrower invoice map from database rows."""
        try:
            with SessionLocal() as db:
                rows = db.execute(
                    text(
                        """
                        SELECT
                            CAST(i.customer_id AS TEXT) AS customer_id,
                            c.name AS customer_name,
                            COALESCE(c.industry, 'unknown') AS industry,
                            COALESCE(c.credit_score, 650) AS credit_score,
                            COALESCE(c.avg_days_to_pay, 30) AS avg_days_to_pay,
                            COALESCE(c.payment_terms, 30) AS payment_terms,
                            COALESCE(c.num_late_payments, 0) AS num_late_payments,
                            i.invoice_number AS invoice_id,
                            COALESCE(i.outstanding_amount, i.amount) AS amount,
                            i.days_overdue,
                            i.status
                        FROM invoices i
                        LEFT JOIN customers c ON c.id = i.customer_id
                        WHERE i.status IN ('open', 'overdue')
                        ORDER BY i.customer_id, i.days_overdue DESC
                        """
                    )
                ).mappings().all()
            if rows:
                customer_map: dict[str, dict] = {}
                portfolio_total = 0.0
                for row in rows:
                    cid = str(row["customer_id"])
                    amount = float(row["amount"] or 0)
                    days_overdue = int(row["days_overdue"] or 0)
                    delay_prob = round(min(0.95, max(0.05, days_overdue / 45.0)), 4)
                    pay_30 = round(1.0 - delay_prob, 4)
                    risk_label = "High" if days_overdue >= 30 else "Medium" if days_overdue >= 10 else "Low"
                    if cid not in customer_map:
                        customer_map[cid] = {
                            "customer_id": cid,
                            "customer_name": str(row["customer_name"] or f"Customer {cid}"),
                            "industry": str(row["industry"] or "unknown"),
                            "credit_score": int(row["credit_score"] or 650),
                            "avg_days_to_pay": float(row["avg_days_to_pay"] or 30),
                            "payment_terms": int(row["payment_terms"] or 30),
                            "num_late_payments": int(row["num_late_payments"] or 0),
                            "invoices": [],
                        }
                    customer_map[cid]["invoices"].append(
                        BorrowerInvoiceSummary(
                            invoice_id=str(row["invoice_id"]),
                            amount=amount,
                            days_overdue=days_overdue,
                            status=str(row["status"]),
                            risk_label=risk_label,
                            delay_probability=delay_prob,
                            pay_30_days=pay_30,
                            recommended_action=self._recommended_action_for_days_overdue(days_overdue),
                        )
                    )
                    portfolio_total += amount
                return customer_map, portfolio_total
        except Exception:
            logger.warning("Failed loading borrower portfolio from DB, using fallback")
            raw = load_invoices_from_json()
            customer_map = {}
            portfolio_total = 0.0
            for row in raw:
                cid = str(row.get("customer_id") or row.get("invoice_id"))
                amount = float(row.get("amount", 0))
                days_overdue = int(row.get("days_overdue", 0))
                delay_prob = round(min(0.95, max(0.05, days_overdue / 45.0)), 4)
                pay_30 = round(1.0 - delay_prob, 4)
                risk_label = "High" if days_overdue >= 30 else "Medium" if days_overdue >= 10 else "Low"
                if cid not in customer_map:
                    customer_map[cid] = {
                        "customer_id": cid,
                        "customer_name": str(row.get("customer_name") or f"Customer {cid}"),
                        "industry": str(row.get("industry") or "unknown"),
                        "credit_score": int(row.get("credit_score") or 650),
                        "avg_days_to_pay": float(row.get("avg_days_to_pay") or 30),
                        "payment_terms": int(row.get("payment_terms") or 30),
                        "num_late_payments": int(row.get("num_late_payments") or 0),
                        "invoices": [],
                    }
                customer_map[cid]["invoices"].append(
                    BorrowerInvoiceSummary(
                        invoice_id=str(row.get("invoice_id")),
                        amount=amount,
                        days_overdue=days_overdue,
                        status=str(row.get("status", "open")),
                        risk_label=risk_label,
                        delay_probability=delay_prob,
                        pay_30_days=pay_30,
                        recommended_action=self._recommended_action_for_days_overdue(days_overdue),
                    )
                )
                portfolio_total += amount
            return customer_map, portfolio_total

    def get_portfolio_total_outstanding(self) -> float:
        customer_map, portfolio_total = self._load_portfolio_customer_map()
        if customer_map:
            return round(portfolio_total, 2)
        return 0.0

    def get_borrower_request_by_customer_id(
        self, customer_id: str
    ) -> Optional[BorrowerPredictionRequest]:
        customer_invoices = self._load_borrower_invoices(customer_id)
        if not customer_invoices:
            return None

        try:
            with SessionLocal() as db:
                row = db.execute(
                    text(
                        """
                        SELECT
                            CAST(c.id AS TEXT) AS customer_id,
                            c.name AS customer_name,
                            COALESCE(c.industry, 'unknown') AS industry,
                            COALESCE(c.credit_score, 650) AS credit_score,
                            COALESCE(c.avg_days_to_pay, 30) AS avg_days_to_pay,
                            COALESCE(c.payment_terms, 30) AS payment_terms,
                            COALESCE(c.num_late_payments, 0) AS num_late_payments
                        FROM customers c
                        WHERE CAST(c.id AS TEXT) = :customer_id
                        LIMIT 1
                        """
                    ),
                    {"customer_id": str(customer_id)},
                ).mappings().one_or_none()
            if row:
                return BorrowerPredictionRequest(
                    customer_id=str(row["customer_id"]),
                    customer_name=str(row["customer_name"]),
                    industry=str(row["industry"]),
                    credit_score=int(row["credit_score"]),
                    avg_days_to_pay=float(row["avg_days_to_pay"]),
                    payment_terms=int(row["payment_terms"]),
                    num_late_payments=int(row["num_late_payments"]),
                    invoices=customer_invoices,
                )
        except Exception:
            logger.warning("Failed loading borrower profile from DB, using fallback")
            raw = load_invoices_from_json()
            rows = [r for r in raw if str(r.get("customer_id") or r.get("invoice_id")) == str(customer_id)]
            if rows:
                row = rows[0]
                return BorrowerPredictionRequest(
                    customer_id=str(customer_id),
                    customer_name=str(row.get("customer_name") or f"Customer {customer_id}"),
                    industry=str(row.get("industry", "unknown")),
                    credit_score=int(row.get("credit_score", 650)),
                    avg_days_to_pay=float(row.get("avg_days_to_pay", 30)),
                    payment_terms=int(row.get("payment_terms", 30)),
                    num_late_payments=int(row.get("num_late_payments", 0)),
                    invoices=customer_invoices,
                )
            return None

    @staticmethod
    def _recommended_action_for_days_overdue(days_overdue: int) -> str:
        if days_overdue >= 30:
            return "Escalate relationship - legal review"
        if days_overdue >= 10:
            return "Follow-up email and call"
        return "Standard reminder cycle"

    def _relationship_action(
        self,
        risk_tier: str,
        total_outstanding: float,
        overdue_count: int,
        delay_prob: float,
        nach: bool,
    ) -> str:
        if risk_tier == "High" and total_outstanding > 100_000:
            return "Escalate Relationship — Legal Review"
        if risk_tier == "High" and delay_prob > 0.75:
            return "Suspend Credit Facility + Demand Letter"
        if risk_tier == "High" and nach:
            return "Activate NACH Mandate + Collection Call"
        if risk_tier == "High":
            return "Place on Credit Hold + Escalate"
        if risk_tier == "Medium" and overdue_count >= 2:
            return "Collection Call + Payment Plan"
        if risk_tier == "Medium":
            return "Follow-up Email + Call"
        return "Standard Reminder Cycle"

    def _build_summary(
        self,
        req: BorrowerPredictionRequest,
        risk_tier: str,
        risk_score: int,
        delay_prob: float,
        recovery: float,
        recovery_rate: float,
        total: float,
        overdue_count: int,
        escalate: bool,
    ) -> str:
        return (
            f"{req.customer_name} carries a total AR exposure of "
            f"${total:,.0f} across {len(req.invoices)} open invoices "
            f"({overdue_count} overdue). "
            f"Borrower risk score is {risk_score}/100 ({risk_tier} tier) with a "
            f"weighted delay probability of {delay_prob:.0%}. "
            f"Expected 30-day recovery is ${recovery:,.0f} "
            f"({recovery_rate:.0%} of outstanding). "
            f"{'Escalation is recommended. ' if escalate else ''}"
            f"Industry: {req.industry}."
        )

    def _empty_borrower_response(
        self, req: BorrowerPredictionRequest
    ) -> BorrowerPredictionResponse:
        return BorrowerPredictionResponse(
            customer_id=str(req.customer_id),
            customer_name=req.customer_name,
            industry=req.industry,
            total_outstanding=0.0,
            total_overdue=0.0,
            open_invoice_count=0,
            overdue_invoice_count=0,
            concentration_pct=0.0,
            weighted_delay_probability=0.0,
            borrower_risk_score=0,
            borrower_risk_tier="Low",
            expected_recovery_amount=0.0,
            expected_recovery_rate=0.0,
            at_risk_amount=0.0,
            recovery_confidence="High",
            borrower_dso=req.avg_days_to_pay,
            dso_vs_portfolio="On Par",
            escalation_recommended=False,
            nach_recommended=False,
            relationship_action="No Open Invoices",
            invoices=[],
            borrower_summary=f"{req.customer_name} has no open invoices.",
            model_version="borrower-rule-v1",
            prediction_source="rule-based",
            llm_refined=False,
            used_fallback=True,
            explanation="Phase 3 fallback: no open invoices available for ML/LLM borrower scoring.",
        )
