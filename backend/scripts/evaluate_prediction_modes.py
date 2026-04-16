"""
Evaluate delay prediction quality across:
  1) ML-only (ml-service /predict/delay)
  2) ML+LLM (backend /predict/delay)
  3) Rule-based (DelayService._rule_based_delay)

Ground truth (for current dataset):
  delayed_true = 1 if invoice.status == 'overdue' else 0
"""

from __future__ import annotations

import asyncio
import json
import math
import urllib.request
from dataclasses import dataclass

from sqlalchemy import text

from app.core.database import SessionLocal
from app.schemas.delay import DelayPredictionRequest
from app.services.delay_service import DelayService

ML_BASE = "http://localhost:8001"
BACKEND_BASE = "http://localhost:8000"


@dataclass
class Row:
    invoice_id: str
    amount: float
    days_overdue: int
    status: str
    payment_terms: int
    credit_score: int
    avg_days_to_pay: float
    num_late_payments: int
    customer_total_overdue: float


def fetch_rows() -> list[Row]:
    sql = """
    SELECT
        i.invoice_number AS invoice_id,
        COALESCE(i.outstanding_amount, i.amount) AS amount,
        i.days_overdue,
        i.status,
        COALESCE(c.payment_terms, 30) AS payment_terms,
        COALESCE(c.credit_score, 650) AS credit_score,
        COALESCE(c.avg_days_to_pay, 30) AS avg_days_to_pay,
        COALESCE(c.num_late_payments, 0) AS num_late_payments,
        COALESCE(c.total_overdue, 0) AS customer_total_overdue
    FROM invoices i
    LEFT JOIN customers c ON c.id = i.customer_id
    WHERE i.status IN ('open', 'overdue', 'paid')
    ORDER BY i.invoice_number
    """
    with SessionLocal() as db:
        rs = db.execute(text(sql)).mappings().all()
    return [
        Row(
            invoice_id=str(r["invoice_id"]),
            amount=float(r["amount"] or 0),
            days_overdue=int(r["days_overdue"] or 0),
            status=str(r["status"] or "open"),
            payment_terms=int(r["payment_terms"] or 30),
            credit_score=max(300, int(r["credit_score"] or 650)),
            avg_days_to_pay=float(r["avg_days_to_pay"] or 30),
            num_late_payments=int(r["num_late_payments"] or 0),
            customer_total_overdue=float(r["customer_total_overdue"] or 0),
        )
        for r in rs
    ]


def make_payload(row: Row) -> dict:
    return {
        "invoice_id": row.invoice_id,
        "invoice_amount": max(row.amount, 1.0),
        "days_overdue": max(row.days_overdue, 0),
        "payment_terms": row.payment_terms,
        "customer_avg_invoice_amount": max(row.amount, 1.0),
        "customer_credit_score": row.credit_score,
        "customer_avg_days_to_pay": row.avg_days_to_pay,
        "num_late_payments": row.num_late_payments,
        "customer_total_overdue": row.customer_total_overdue,
        "behavior_type": "Chronic Delayed Payer" if row.days_overdue >= 30 else "Occasional Late Payer",
        "on_time_ratio": max(0.0, min(100.0, 100.0 - row.days_overdue)),
        "avg_delay_days_historical": row.avg_days_to_pay,
        "behavior_risk_score": min(100.0, row.days_overdue * 1.2),
        "deterioration_trend": 0.2 if row.days_overdue >= 30 else 0.0,
        "followup_dependency": row.days_overdue >= 10,
    }


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def auc_roc(scores: list[float], labels: list[int]) -> float:
    pos = [(s, y) for s, y in zip(scores, labels) if y == 1]
    neg = [(s, y) for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    for ps, _ in pos:
        for ns, _ in neg:
            if ps > ns:
                wins += 1.0
            elif ps == ns:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def metric_block(scores: list[float], labels: list[int], threshold: float = 0.5) -> dict:
    preds = [1 if s >= threshold else 0 for s in scores]
    tp = sum(1 for p, y in zip(preds, labels) if p == 1 and y == 1)
    tn = sum(1 for p, y in zip(preds, labels) if p == 0 and y == 0)
    fp = sum(1 for p, y in zip(preds, labels) if p == 1 and y == 0)
    fn = sum(1 for p, y in zip(preds, labels) if p == 0 and y == 1)
    n = max(len(labels), 1)

    acc = (tp + tn) / n
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (2 * precision * recall) / max(precision + recall, 1e-9)
    brier = sum((s - y) ** 2 for s, y in zip(scores, labels)) / n
    auc = auc_roc(scores, labels)
    return {
        "n": n,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier": brier,
        "auc_roc": auc,
    }


def pct(x: float) -> str:
    if math.isnan(x):
        return "nan"
    return f"{x*100:.2f}%"


async def main() -> int:
    rows = fetch_rows()
    if not rows:
        print("No invoices found for evaluation.")
        return 1

    delay_svc = DelayService()
    labels = [1 if r.status == "overdue" else 0 for r in rows]

    scores_ml: list[float] = []
    scores_ml_llm: list[float] = []
    scores_rule: list[float] = []

    for r in rows:
        payload = make_payload(r)

        ml_resp = post_json(f"{ML_BASE}/predict/delay", payload)
        ml_score = float(ml_resp.get("delay_probability", 0.0))
        scores_ml.append(ml_score)

        ml_llm_resp = post_json(f"{BACKEND_BASE}/predict/delay", payload)
        ml_llm_score = float(ml_llm_resp.get("delay_probability", 0.0))
        scores_ml_llm.append(ml_llm_score)

        rule_req = DelayPredictionRequest(**payload)
        rule_resp = delay_svc._rule_based_delay(rule_req)  # intentional for pure fallback benchmark
        scores_rule.append(float(rule_resp.delay_probability))

    m_ml = metric_block(scores_ml, labels)
    m_ml_llm = metric_block(scores_ml_llm, labels)
    m_rule = metric_block(scores_rule, labels)

    print("Delay Prediction Evaluation (Truth: status == overdue)")
    print("-" * 88)
    print(f"{'Mode':<14} {'Acc':>8} {'Prec':>8} {'Recall':>8} {'F1':>8} {'AUC':>8} {'Brier':>10}")
    print("-" * 88)
    print(
        f"{'ml':<14} {pct(m_ml['accuracy']):>8} {pct(m_ml['precision']):>8} {pct(m_ml['recall']):>8} "
        f"{pct(m_ml['f1']):>8} {pct(m_ml['auc_roc']):>8} {m_ml['brier']:>10.4f}"
    )
    print(
        f"{'ml+llm':<14} {pct(m_ml_llm['accuracy']):>8} {pct(m_ml_llm['precision']):>8} {pct(m_ml_llm['recall']):>8} "
        f"{pct(m_ml_llm['f1']):>8} {pct(m_ml_llm['auc_roc']):>8} {m_ml_llm['brier']:>10.4f}"
    )
    print(
        f"{'rule-based':<14} {pct(m_rule['accuracy']):>8} {pct(m_rule['precision']):>8} {pct(m_rule['recall']):>8} "
        f"{pct(m_rule['f1']):>8} {pct(m_rule['auc_roc']):>8} {m_rule['brier']:>10.4f}"
    )
    print("-" * 88)

    delta_f1 = m_ml_llm["f1"] - m_ml["f1"]
    delta_auc = m_ml_llm["auc_roc"] - m_ml["auc_roc"] if not math.isnan(m_ml["auc_roc"]) and not math.isnan(m_ml_llm["auc_roc"]) else 0.0
    delta_brier = m_ml_llm["brier"] - m_ml["brier"]  # lower is better

    print("LLM impact vs ML baseline:")
    print(f"- F1 delta     : {delta_f1:+.4f} ({'helping' if delta_f1 > 0 else 'hurting' if delta_f1 < 0 else 'neutral'})")
    print(f"- AUC delta    : {delta_auc:+.4f} ({'helping' if delta_auc > 0 else 'hurting' if delta_auc < 0 else 'neutral'})")
    print(f"- Brier delta  : {delta_brier:+.4f} ({'helping' if delta_brier < 0 else 'hurting' if delta_brier > 0 else 'neutral'})")
    print(f"- Sample count : {m_ml['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
