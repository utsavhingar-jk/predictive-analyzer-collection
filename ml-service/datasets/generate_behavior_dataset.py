"""
Synthetic customer-level behavior rows for XGBoost multiclass training.

Labels match the rule order in main.py /analyze/payment-behavior (6 classes).
"""

import random

import numpy as np
import pandas as pd
from pathlib import Path

random.seed(43)
np.random.seed(43)

OUTPUT_PATH = Path(__file__).parent / "behavior_training.csv"
# Base synthetic rows + deterministic edge rows (rule boundaries / rare mixes)
N_RECORDS = 7500
EDGE_RECORDS = 1200

ACK_BEHAVIOR_MAP = {
    "normal": 0,
    "delayed": 1,
    "ignored": 2,
    "disputed": 3,
}

# Must match inference/behavior_predictor.py BEHAVIOR_CLASSES
BEHAVIOR_CLASSES = [
    "Consistent Payer",
    "Occasional Late Payer",
    "Reminder Driven Payer",
    "Partial Payment Payer",
    "Chronic Delayed Payer",
    "High Risk Defaulter",
]


def classify_behavior_label(
    historical_on_time_ratio: float,
    avg_delay_days: float,
    partial_payment_frequency: float,
    payment_after_followup_count: int,
    total_invoices: int,
    deterioration_trend: float,
    transaction_success_failure_pattern: float,
) -> int:
    """Mirror main.py rule priority → class index."""
    on_time_pct = historical_on_time_ratio * 100
    followup_ratio = payment_after_followup_count / max(total_invoices, 1)

    raw = (
        (1 - historical_on_time_ratio) * 0.25
        + min(1.0, avg_delay_days / 60) * 0.25
        + followup_ratio * 0.15
        + partial_payment_frequency * 0.10
        + max(0.0, deterioration_trend) * 0.10
        + transaction_success_failure_pattern * 0.15
    )
    behavior_risk_score = min(100.0, raw * 100)

    if on_time_pct >= 85 and avg_delay_days < 5:
        return 0
    if on_time_pct >= 65 and avg_delay_days < 15:
        return 1
    if followup_ratio >= 0.5:
        return 2
    if partial_payment_frequency >= 0.4:
        return 3
    if on_time_pct < 35 or avg_delay_days > 30:
        return 4
    if behavior_risk_score >= 75:
        return 5
    return 1


def generate_edge_row(seq: int) -> dict:
    """
    Hand-tuned feature vectors near decision boundaries; label = classify_behavior_label(...).
    Cycles through EDGE_TEMPLATES for coverage of all classes and ambiguous zones.
    """
    tid = seq % len(EDGE_TEMPLATES)
    (
        historical_on_time_ratio,
        avg_delay_days,
        repayment_consistency,
        partial_payment_frequency,
        prior_delayed_invoice_count,
        payment_after_followup_count,
        total_invoices,
        deterioration_trend,
        transaction_success_failure_pattern,
        invoice_ack,
    ) = EDGE_TEMPLATES[tid]

    y = classify_behavior_label(
        historical_on_time_ratio,
        avg_delay_days,
        partial_payment_frequency,
        payment_after_followup_count,
        total_invoices,
        deterioration_trend,
        transaction_success_failure_pattern,
    )

    return {
        "customer_id": f"CUST-BEH-E{seq:05d}",
        "historical_on_time_ratio": round(historical_on_time_ratio, 4),
        "avg_delay_days": round(avg_delay_days, 2),
        "repayment_consistency": round(repayment_consistency, 4),
        "partial_payment_frequency": round(partial_payment_frequency, 4),
        "prior_delayed_invoice_count": prior_delayed_invoice_count,
        "payment_after_followup_count": payment_after_followup_count,
        "total_invoices": total_invoices,
        "deterioration_trend": round(deterioration_trend, 4),
        "transaction_success_failure_pattern": round(transaction_success_failure_pattern, 4),
        "invoice_acknowledgement_encoded": invoice_ack,
        "behavior_class": y,
    }


# (on_time, avg_delay, repay_consist, partial_freq, prior_delayed, pay_after_fu, total_inv, deter, tsf, ack_encoded)
EDGE_TEMPLATES = [
    # Class 0 — strong payer band
    (0.91, 2.0, 0.92, 0.02, 1, 1, 25, -0.05, 0.05, 0),
    (0.86, 4.2, 0.88, 0.04, 2, 2, 30, -0.02, 0.06, 0),
    (0.95, 0.8, 0.96, 0.01, 0, 0, 12, -0.1, 0.02, 0),
    (0.88, 4.9, 0.85, 0.03, 3, 2, 18, 0.0, 0.04, 1),
    # Near 0/1 boundary (on_time ~85, delay around 5)
    (0.855, 4.8, 0.82, 0.06, 4, 3, 22, 0.02, 0.08, 0),
    (0.84, 5.2, 0.80, 0.07, 5, 4, 24, 0.03, 0.09, 0),
    # Class 1 — moderate
    (0.72, 8.0, 0.75, 0.12, 8, 6, 35, 0.05, 0.12, 0),
    (0.68, 12.0, 0.70, 0.14, 10, 8, 40, 0.08, 0.14, 1),
    (0.78, 10.5, 0.78, 0.10, 6, 5, 28, 0.04, 0.10, 0),
    (0.66, 14.0, 0.68, 0.16, 11, 9, 42, 0.09, 0.15, 0),
    # Class 2 — follow-up driven (ensure rules 1–2 don’t fire first)
    (0.55, 22.0, 0.50, 0.18, 14, 20, 35, 0.12, 0.22, 0),
    (0.48, 25.0, 0.45, 0.20, 16, 22, 40, 0.14, 0.25, 1),
    (0.52, 18.0, 0.48, 0.17, 12, 18, 32, 0.11, 0.20, 0),
    (0.50, 28.0, 0.46, 0.19, 15, 20, 38, 0.13, 0.24, 2),
    # Class 3 — partial payers (keep followup < 0.5 so rule 3 doesn’t steal)
    (0.58, 16.0, 0.55, 0.42, 10, 8, 30, 0.10, 0.18, 0),
    (0.52, 20.0, 0.48, 0.45, 12, 9, 28, 0.11, 0.20, 0),
    (0.60, 14.0, 0.58, 0.50, 9, 7, 26, 0.08, 0.16, 1),
    (0.54, 18.0, 0.52, 0.44, 11, 8, 29, 0.09, 0.17, 0),
    # Class 4 — chronic delay / very low on-time (avoid triggering 3 first: partial < 0.4)
    (0.32, 35.0, 0.35, 0.28, 22, 14, 40, 0.22, 0.38, 0),
    (0.30, 42.0, 0.32, 0.30, 24, 15, 42, 0.25, 0.40, 1),
    (0.34, 38.0, 0.36, 0.27, 21, 13, 38, 0.21, 0.37, 0),
    (0.28, 48.0, 0.30, 0.32, 26, 16, 44, 0.28, 0.42, 2),
    # Class 5 — high composite score path
    (0.48, 26.0, 0.40, 0.35, 18, 16, 32, 0.35, 0.55, 0),
    (0.45, 28.0, 0.38, 0.36, 19, 17, 34, 0.38, 0.58, 0),
    (0.50, 24.0, 0.42, 0.34, 17, 15, 30, 0.33, 0.52, 1),
    (0.42, 30.0, 0.36, 0.38, 20, 18, 36, 0.40, 0.60, 0),
    # Ambiguous middle (often class 1)
    (0.62, 16.5, 0.65, 0.22, 9, 7, 33, 0.06, 0.13, 0),
    (0.64, 15.0, 0.67, 0.20, 8, 6, 31, 0.05, 0.12, 0),
    # Sparse history
    (0.80, 6.0, 0.82, 0.08, 1, 1, 5, 0.0, 0.07, 0),
    (0.40, 32.0, 0.38, 0.26, 6, 5, 8, 0.20, 0.35, 0),
    # Extreme excellent vs terrible
    (0.98, 0.5, 0.99, 0.0, 0, 0, 8, -0.15, 0.01, 0),
    (0.22, 55.0, 0.22, 0.45, 30, 25, 35, 0.45, 0.72, 2),
    # More follow-up / partial boundary cases
    (0.62, 12.0, 0.62, 0.38, 7, 14, 28, 0.07, 0.14, 0),
    (0.58, 14.0, 0.58, 0.41, 9, 12, 26, 0.08, 0.15, 0),
    (0.56, 13.0, 0.56, 0.39, 8, 11, 25, 0.07, 0.14, 1),
]


def generate_row(i: int) -> dict:
    total_invoices = random.randint(3, 80)
    # Dedicated "High Risk Defaulter" band — coherent features + label 5
    if random.random() < 0.11:
        historical_on_time_ratio = float(np.random.uniform(0.40, 0.62))
        avg_delay_days = float(np.random.uniform(12, 28))
        repayment_consistency = float(np.random.uniform(0.2, 0.55))
        partial_payment_frequency = float(np.random.uniform(0.15, 0.38))
        prior_delayed_invoice_count = int(total_invoices * np.random.uniform(0.35, 0.7))
        payment_after_followup_count = int(total_invoices * np.random.uniform(0.35, 0.48))
        deterioration_trend = float(np.random.uniform(0.15, 0.45))
        transaction_success_failure_pattern = float(np.random.uniform(0.35, 0.75))
        y = 5
    else:
        # Bias ~15% of rows toward excellent payers so class 0 is learnable
        if random.random() < 0.15:
            historical_on_time_ratio = float(np.clip(np.random.uniform(0.88, 0.99), 0.05, 0.99))
            avg_delay_days = float(np.random.uniform(0.5, 4.5))
        else:
            historical_on_time_ratio = float(np.clip(np.random.beta(4, 3), 0.05, 0.99))
            avg_delay_days = float(np.random.exponential(12) + np.random.uniform(0, 8))
        repayment_consistency = float(np.clip(np.random.beta(3, 2), 0.05, 0.99))
        partial_payment_frequency = float(np.clip(np.random.beta(2, 5), 0.0, 0.95))
        prior_delayed_invoice_count = int(total_invoices * np.random.uniform(0, 0.6))
        payment_after_followup_count = int(total_invoices * np.random.uniform(0, 0.55))
        deterioration_trend = float(np.random.uniform(-0.4, 0.5))
        transaction_success_failure_pattern = float(np.clip(np.random.beta(2, 8), 0.0, 0.9))
        y = classify_behavior_label(
            historical_on_time_ratio,
            avg_delay_days,
            partial_payment_frequency,
            payment_after_followup_count,
            total_invoices,
            deterioration_trend,
            transaction_success_failure_pattern,
        )

    ack = random.choices(
        ["normal", "delayed", "ignored", "disputed"],
        weights=[0.62, 0.20, 0.12, 0.06],
    )[0]

    return {
        "customer_id": f"CUST-BEH-{i:05d}",
        "historical_on_time_ratio": round(historical_on_time_ratio, 4),
        "avg_delay_days": round(avg_delay_days, 2),
        "repayment_consistency": round(repayment_consistency, 4),
        "partial_payment_frequency": round(partial_payment_frequency, 4),
        "prior_delayed_invoice_count": prior_delayed_invoice_count,
        "payment_after_followup_count": payment_after_followup_count,
        "total_invoices": total_invoices,
        "deterioration_trend": round(deterioration_trend, 4),
        "transaction_success_failure_pattern": round(transaction_success_failure_pattern, 4),
        "invoice_acknowledgement_encoded": ACK_BEHAVIOR_MAP[ack],
        "behavior_class": y,
    }


def main() -> None:
    rows = [generate_row(i + 1) for i in range(N_RECORDS)]
    rows.extend([generate_edge_row(i + 1) for i in range(EDGE_RECORDS)])
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} rows ({N_RECORDS} random + {EDGE_RECORDS} edge) to {OUTPUT_PATH}")
    print(df["behavior_class"].value_counts().sort_index())


if __name__ == "__main__":
    main()
