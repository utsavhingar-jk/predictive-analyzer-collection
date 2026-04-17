"""
Evaluate delay prediction quality on pre-due synthetic snapshots.

Modes:
  1) ml-direct           -> ml-service /predict/delay
  2) backend-final       -> backend /predict/delay
  3) rule-direct         -> DelayService._rule_based_delay

The synthetic dataset target is future-looking:
  will_be_late_in_30_days = 1 if the invoice later becomes late

Important:
  - evaluation payloads simulate a prediction BEFORE the invoice is due
  - days_overdue is forced to 0 to avoid outcome leakage
  - backend rows are split by llm_used so ML passthrough and ML+LLM are not conflated
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.delay import DelayPredictionRequest
from app.services.delay_service import DelayService

ML_BASE = "http://localhost:8001"
BACKEND_BASE = "http://localhost:8000"
DATASET_PATH = Path(__file__).resolve().parents[2] / "ml-service" / "datasets" / "invoices.csv"


@dataclass
class Row:
    invoice_id: str
    invoice_amount: float
    payment_terms: int
    customer_credit_score: int
    customer_avg_days_to_pay: float
    num_previous_invoices: int
    num_late_payments: int
    industry_encoded: int
    customer_total_overdue: float
    delay_probability_target: float
    will_be_late_in_30_days: int


def load_rows() -> list[Row]:
    if not DATASET_PATH.exists():
        raise RuntimeError(
            f"Missing synthetic dataset at {DATASET_PATH}. "
            "Run: python3 ml-service/datasets/generate_dataset.py"
        )

    rows: list[Row] = []
    with DATASET_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rows.append(
                Row(
                    invoice_id=str(raw["invoice_id"]),
                    invoice_amount=float(raw["invoice_amount"]),
                    payment_terms=max(1, int(raw["payment_terms"])),
                    customer_credit_score=max(300, int(raw["customer_credit_score"])),
                    customer_avg_days_to_pay=float(raw["customer_avg_days_to_pay"]),
                    num_previous_invoices=max(1, int(raw["num_previous_invoices"])),
                    num_late_payments=max(0, int(raw["num_late_payments"])),
                    industry_encoded=int(raw["industry_encoded"]),
                    customer_total_overdue=max(0.0, float(raw["customer_total_overdue"])),
                    delay_probability_target=float(raw["delay_probability_target"]),
                    will_be_late_in_30_days=int(raw.get("will_be_late_in_30_days", "0")),
                )
            )
    return rows


def industry_name(code: int) -> str:
    mapping = {
        0: "manufacturing",
        1: "technology",
        2: "healthcare",
        3: "retail",
        4: "logistics",
        5: "real estate",
        6: "construction",
        7: "agriculture",
        8: "finance",
        9: "pharma",
    }
    return mapping.get(code, "unknown")


def synthetic_behavior_context(row: Row) -> dict:
    late_rate = row.num_late_payments / max(row.num_previous_invoices, 1)
    terms_gap = max(0.0, row.customer_avg_days_to_pay - row.payment_terms)
    terms_stress = terms_gap / max(row.payment_terms, 1)
    exposure_ratio = row.customer_total_overdue / max(row.invoice_amount, 1.0)

    if late_rate >= 0.45 or terms_stress >= 0.45:
        behavior_type = "Chronic Delayed Payer"
    elif late_rate >= 0.32:
        behavior_type = "Reminder Driven Payer"
    elif late_rate >= 0.20 or terms_stress >= 0.20:
        behavior_type = "Occasional Late Payer"
    else:
        behavior_type = "Consistent Payer"

    on_time_ratio = max(5.0, min(99.0, (1.0 - late_rate) * 100.0))
    behavior_risk_score = min(
        100.0,
        late_rate * 55.0 + terms_stress * 30.0 + min(exposure_ratio, 3.0) * 8.0,
    )
    deterioration_trend = min(0.6, max(0.0, late_rate * 0.7 + terms_stress * 0.4 - 0.1))

    return {
        "behavior_type": behavior_type,
        "on_time_ratio": round(on_time_ratio, 1),
        "avg_delay_days_historical": round(row.customer_avg_days_to_pay, 1),
        "behavior_risk_score": round(behavior_risk_score, 1),
        "deterioration_trend": round(deterioration_trend, 3),
        "followup_dependency": late_rate >= 0.35,
    }


def make_payload(row: Row) -> dict:
    payload = {
        "invoice_id": row.invoice_id,
        "invoice_amount": max(row.invoice_amount, 1.0),
        # Pre-due snapshot: this is what removes current-outcome leakage.
        "days_overdue": 0,
        "payment_terms": row.payment_terms,
        "customer_avg_invoice_amount": max(row.invoice_amount, 1.0),
        "customer_credit_score": row.customer_credit_score,
        "customer_avg_days_to_pay": row.customer_avg_days_to_pay,
        "num_previous_invoices": row.num_previous_invoices,
        "num_late_payments": row.num_late_payments,
        "industry": industry_name(row.industry_encoded),
        "customer_total_overdue": row.customer_total_overdue,
    }
    payload.update(synthetic_behavior_context(row))
    return payload


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
    if not labels:
        return {
            "n": 0,
            "accuracy": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "f1": float("nan"),
            "brier": float("nan"),
            "auc_roc": float("nan"),
        }
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
        "n": len(labels),
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
    return f"{x * 100:.2f}%"


def print_metric_line(name: str, metrics: dict) -> None:
    print(
        f"{name:<20} {metrics['n']:>6} {pct(metrics['accuracy']):>8} "
        f"{pct(metrics['precision']):>8} {pct(metrics['recall']):>8} "
        f"{pct(metrics['f1']):>8} {pct(metrics['auc_roc']):>8} {metrics['brier']:>10.4f}"
    )


def main() -> int:
    rows = load_rows()
    limit = int(os.getenv("EVAL_LIMIT", "0") or 0)
    if limit > 0:
        rows = rows[:limit]
    if not rows:
        print("No synthetic invoice rows found for evaluation.")
        return 1

    delay_svc = DelayService()

    labels_all: list[int] = []
    scores_ml_direct: list[float] = []
    scores_backend_final: list[float] = []
    scores_rule_direct: list[float] = []

    labels_llm_used: list[int] = []
    scores_ml_on_llm_rows: list[float] = []
    scores_ml_llm: list[float] = []

    labels_backend_ml: list[int] = []
    scores_backend_ml: list[float] = []

    labels_backend_rule: list[int] = []
    scores_backend_rule: list[float] = []

    for row in rows:
        payload = make_payload(row)
        label = row.will_be_late_in_30_days
        labels_all.append(label)

        try:
            ml_resp = post_json(f"{ML_BASE}/predict/delay", payload)
            ml_score = float(ml_resp.get("delay_probability", 0.0))
            scores_ml_direct.append(ml_score)

            backend_resp = post_json(f"{BACKEND_BASE}/predict/delay", payload)
            backend_score = float(backend_resp.get("delay_probability", 0.0))
            scores_backend_final.append(backend_score)
        except Exception as exc:
            raise RuntimeError(
                f"Evaluation failed for invoice_id={row.invoice_id} with payload={payload}"
            ) from exc

        rule_req = DelayPredictionRequest(**payload)
        rule_resp = delay_svc._rule_based_delay(rule_req)  # intentional pure fallback benchmark
        scores_rule_direct.append(float(rule_resp.delay_probability))

        if bool(backend_resp.get("llm_used", False)):
            labels_llm_used.append(label)
            scores_ml_on_llm_rows.append(ml_score)
            scores_ml_llm.append(backend_score)
        elif backend_resp.get("prediction_source") == "ml":
            labels_backend_ml.append(label)
            scores_backend_ml.append(backend_score)
        elif backend_resp.get("prediction_source") == "rule-based":
            labels_backend_rule.append(label)
            scores_backend_rule.append(backend_score)

    m_ml_direct = metric_block(scores_ml_direct, labels_all)
    m_backend_final = metric_block(scores_backend_final, labels_all)
    m_rule_direct = metric_block(scores_rule_direct, labels_all)
    m_ml_llm = metric_block(scores_ml_llm, labels_llm_used)
    m_ml_on_llm_rows = metric_block(scores_ml_on_llm_rows, labels_llm_used)
    m_backend_ml = metric_block(scores_backend_ml, labels_backend_ml)
    m_backend_rule = metric_block(scores_backend_rule, labels_backend_rule)

    print("Delay Evaluation — Pre-Due Synthetic Snapshot")
    print("Truth label: will_be_late_in_30_days")
    print("-" * 104)
    print(f"{'Mode':<20} {'N':>6} {'Acc':>8} {'Prec':>8} {'Recall':>8} {'F1':>8} {'AUC':>8} {'Brier':>10}")
    print("-" * 104)
    print_metric_line("ml-direct", m_ml_direct)
    print_metric_line("backend-final", m_backend_final)
    print_metric_line("rule-direct", m_rule_direct)
    print_metric_line("backend-ml", m_backend_ml)
    print_metric_line("backend-rule", m_backend_rule)
    print_metric_line("ml+llm", m_ml_llm)
    print_metric_line("ml-on-llm-rows", m_ml_on_llm_rows)
    print("-" * 104)

    if m_ml_llm["n"] > 0 and m_ml_on_llm_rows["n"] > 0:
        delta_f1 = m_ml_llm["f1"] - m_ml_on_llm_rows["f1"]
        delta_auc = (
            m_ml_llm["auc_roc"] - m_ml_on_llm_rows["auc_roc"]
            if not math.isnan(m_ml_llm["auc_roc"]) and not math.isnan(m_ml_on_llm_rows["auc_roc"])
            else float("nan")
        )
        delta_brier = m_ml_llm["brier"] - m_ml_on_llm_rows["brier"]

        print("Validated LLM impact on rows where llm_used=true:")
        print(f"- F1 delta    : {delta_f1:+.4f}")
        print(f"- AUC delta   : {delta_auc:+.4f}" if not math.isnan(delta_auc) else "- AUC delta   : nan")
        print(f"- Brier delta : {delta_brier:+.4f} (lower is better)")
    else:
        print("Validated LLM impact on rows where llm_used=true: insufficient rows.")

    print(f"- Total synthetic rows evaluated: {len(rows)}")
    print(f"- Backend rows with llm_used=true: {m_ml_llm['n']}")
    print(f"- Backend rows with ML passthrough: {m_backend_ml['n']}")
    print(f"- Backend rows with rule fallback: {m_backend_rule['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
