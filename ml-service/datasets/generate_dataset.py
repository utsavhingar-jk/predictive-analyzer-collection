from __future__ import annotations

"""
Dataset Generator — AI Collector (INR, Indian B2B Lending)

Generates a large invoice table for XGBoost (payment, risk, delay) + downstream
borrower aggregation. Includes structured edge cases for boundary behaviour.

Key design decisions:
  - Amounts in INR (wide range including extremes)
  - CIBIL credit score range (300–900)
  - Indian industries with realistic payment behavior profiles
  - Labels derived from features with calibrated noise
  - Extra EDGE_RECORDS cover: boundary amounts/DPD/credit/terms, zero-overdue, deep DPD

Output: invoices.csv
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path

random.seed(42)
np.random.seed(42)

OUTPUT_PATH = Path(__file__).parent / "invoices.csv"
# Base random rows + deterministic edge rows (coverage for training)
N_RECORDS = 10_000
EDGE_RECORDS = 800
N_UNIQUE_CUSTOMERS = 2000

# ── Industry config ───────────────────────────────────────────────────────────
# Each industry has a base delay tendency and typical invoice size range (INR)
INDUSTRIES = {
    0: {"name": "Manufacturing",    "delay_bias": 0.10, "min": 100_000,   "max": 5_000_000},
    1: {"name": "IT/Technology",    "delay_bias": -0.05,"min": 50_000,    "max": 3_000_000},
    2: {"name": "Healthcare",       "delay_bias": 0.05, "min": 75_000,    "max": 2_000_000},
    3: {"name": "Retail/FMCG",     "delay_bias": 0.00, "min": 25_000,    "max": 1_500_000},
    4: {"name": "Logistics",        "delay_bias": 0.08, "min": 50_000,    "max": 2_500_000},
    5: {"name": "Real Estate",      "delay_bias": 0.18, "min": 500_000,   "max": 50_000_000},
    6: {"name": "Construction",     "delay_bias": 0.20, "min": 200_000,   "max": 20_000_000},
    7: {"name": "Agriculture",      "delay_bias": 0.12, "min": 50_000,    "max": 3_000_000},
    8: {"name": "Finance/NBFC",     "delay_bias": -0.08,"min": 100_000,   "max": 10_000_000},
    9: {"name": "Pharma",           "delay_bias": 0.03, "min": 75_000,    "max": 4_000_000},
}

# ── Customer archetypes ────────────────────────────────────────────────────────
# Each archetype maps to a profile of creditworthiness.
# Weights tuned to produce ~40% Low, ~35% Medium, ~25% High risk distribution.
ARCHETYPES = [
    # (weight, cibil_range,   avg_days_to_pay_range, late_pay_rate, label_bias)
    (0.15, (750, 900), (20, 35),  0.02, -0.35),   # Excellent — very reliable
    (0.20, (680, 749), (28, 45),  0.10, -0.12),   # Good — mostly on time
    (0.20, (600, 679), (38, 60),  0.25,  0.08),   # Average — occasional delays
    (0.20, (520, 599), (55, 80),  0.45,  0.32),   # Weak — frequent delays
    (0.15, (400, 519), (70, 110), 0.65,  0.58),   # Poor — chronic defaulters
    (0.10, (300, 399), (90, 150), 0.85,  0.82),   # Very poor — high risk
]

PAYMENT_TERMS_OPTIONS = [30, 45, 60, 90]


def pick_archetype():
    weights = [a[0] for a in ARCHETYPES]
    return random.choices(ARCHETYPES, weights=weights, k=1)[0]


def _delay_prob_and_risk(
    avg_days_to_pay: float,
    payment_terms: int,
    credit_score: int,
    num_prev: int,
    num_late: int,
    customer_total_overdue: float,
    invoice_amount: float,
    industry_code: int,
    label_bias: float,
    noise_scale: float = 0.06,
) -> tuple[float, int, int, int, int, int]:
    """Shared future-looking label logic for payment, delay, and risk targets."""
    ind = INDUSTRIES[industry_code]
    terms_gap = max(0.0, avg_days_to_pay - payment_terms)
    terms_stress = terms_gap / max(payment_terms, 1)
    late_payment_rate = num_late / max(num_prev, 1)
    exposure_ratio = customer_total_overdue / max(invoice_amount * 4, 1)
    amount_stress = min(1.0, np.log1p(invoice_amount) / np.log1p(ind["max"]))
    base_delay_prob = (
        terms_stress * 0.28
        + (1 - credit_score / 900) * 0.24
        + late_payment_rate * 0.22
        + exposure_ratio * 0.12
        + amount_stress * 0.06
        + ind["delay_bias"] * 0.10
        + label_bias * 0.12
    )
    noise = np.random.normal(0, noise_scale)
    delay_prob = float(np.clip(base_delay_prob + noise, 0.01, 0.99))

    will_be_late_in_30_days = int(random.random() < delay_prob)

    p7 = max(0.0, 0.92 - delay_prob * 1.15 - late_payment_rate * 0.18 - terms_stress * 0.12)
    p15 = max(0.0, 0.88 - delay_prob * 0.92 - late_payment_rate * 0.10 - terms_stress * 0.08)
    p30 = max(0.0, 0.84 - delay_prob * 0.74)
    p7, p15, p30 = min(p7, 0.98), min(p15, 0.98), min(p30, 0.98)

    paid_in_7 = int(random.random() < p7)
    paid_in_15 = int(random.random() < p15)
    paid_in_30 = int(random.random() < p30)
    if paid_in_7:
        paid_in_15 = 1
        paid_in_30 = 1
    if paid_in_15:
        paid_in_30 = 1

    if delay_prob >= 0.55:
        risk_label = 2
    elif delay_prob >= 0.28:
        risk_label = 1
    else:
        risk_label = 0
    if random.random() < 0.05:
        risk_label = random.randint(0, 2)

    return delay_prob, will_be_late_in_30_days, paid_in_7, paid_in_15, paid_in_30, risk_label


def generate_record(i: int) -> dict:
    """Generate one synthetic invoice record with realistic correlations."""
    arch_weight, cibil_range, avg_dtp_range, late_rate, label_bias = pick_archetype()

    industry_code = random.randint(0, 9)
    ind = INDUSTRIES[industry_code]

    # ── Invoice amount (INR, log-normal distribution) ─────────────────────────
    log_min = np.log(ind["min"])
    log_max = np.log(ind["max"])
    invoice_amount = round(np.exp(random.uniform(log_min, log_max)), -3)  # round to ₹1000

    # ── Customer signals ──────────────────────────────────────────────────────
    credit_score   = random.randint(*cibil_range)
    avg_days_to_pay = round(random.uniform(*avg_dtp_range), 1)
    payment_terms  = random.choice(PAYMENT_TERMS_OPTIONS)
    num_prev       = random.randint(1, 60)
    num_late       = int(round(num_prev * late_rate * random.uniform(0.6, 1.4)))
    num_late       = max(0, min(num_late, num_prev))

    # ── Customer total overdue (across all their invoices) ────────────────────
    projected_overdue_multiplier = max(0.0, late_rate * random.uniform(0.6, 1.8) + max(label_bias, 0.0))
    customer_total_overdue = round(invoice_amount * projected_overdue_multiplier, -3)

    delay_prob, will_be_late_in_30_days, paid_in_7, paid_in_15, paid_in_30, risk_label = _delay_prob_and_risk(
        avg_days_to_pay,
        payment_terms,
        credit_score,
        num_prev,
        num_late,
        customer_total_overdue,
        invoice_amount,
        industry_code,
        label_bias,
    )

    if will_be_late_in_30_days:
        max_overdue = int(20 + delay_prob * 120 + max(label_bias, 0.0) * 35)
        days_overdue = random.randint(1, max(1, max_overdue))
    else:
        days_overdue = 0

    return {
        "invoice_id":               f"INV-{i:05d}",
        "customer_id":              100 + (i % N_UNIQUE_CUSTOMERS),
        "invoice_amount":           invoice_amount,
        "days_overdue":             days_overdue,
        "customer_credit_score":    credit_score,
        "customer_avg_days_to_pay": avg_days_to_pay,
        "payment_terms":            payment_terms,
        "num_previous_invoices":    num_prev,
        "num_late_payments":        num_late,
        "industry_encoded":         industry_code,
        "customer_total_overdue":   customer_total_overdue,
        "paid_in_7":               paid_in_7,
        "paid_in_15":              paid_in_15,
        "paid_in_30":              paid_in_30,
        "will_be_late_in_30_days": will_be_late_in_30_days,
        "risk_label":              risk_label,
        # Regression target for XGBoost delay model using pre-outcome-safe context.
        "delay_probability_target": round(delay_prob, 6),
        # Extra context columns (used in behavior engine but not in ML features)
        "currency":                "INR",
        "industry_name":           ind["name"],
    }


def generate_edge_record(seq: int) -> dict:
    """
    Deterministic edge cases: boundary DPD, credit, amounts, terms, prev/late counts.
    """
    t = seq % 40
    industry_code = seq % 10
    ind = INDUSTRIES[industry_code]
    label_bias = 0.0

    # Preset grids (amount, days_overdue, credit, terms, num_prev, num_late)
    presets = [
        (25_000, 0, 900, 30, 5, 0),
        (25_000, 0, 300, 30, 2, 0),
        (50_000_000, 0, 750, 90, 40, 1),
        (100_000, 1, 600, 30, 10, 2),
        (500_000, 30, 520, 30, 20, 8),
        (500_000, 31, 520, 45, 20, 9),
        (800_000, 60, 480, 60, 25, 12),
        (800_000, 61, 480, 60, 25, 12),
        (1_200_000, 90, 400, 90, 30, 18),
        (2_000_000, 120, 350, 90, 35, 22),
        (3_500_000, 180, 320, 90, 50, 30),
        (400_000, 0, 850, 15, 1, 0),
        (400_000, 0, 305, 15, 1, 0),
        (150_000, 45, 580, 30, 1, 0),
        (150_000, 45, 580, 30, 60, 55),
        (900_000, 75, 450, 60, 15, 14),
        (2_500_000, 0, 780, 120, 8, 0),
        (75_000, 10, 650, 30, 3, 1),
        (75_000, 10, 650, 30, 3, 3),
        (12_000_000, 95, 410, 90, 22, 20),
        (300_000, 0, 720, 45, 12, 0),
        (300_000, 200, 310, 60, 8, 7),
        (600_000, 0, 880, 30, 50, 0),
        (600_000, 5, 880, 30, 50, 25),
        (950_000, 30, 600, 30, 1, 1),
        (1_100_000, 60, 540, 60, 18, 17),
        (4_000_000, 0, 690, 90, 6, 0),
        (4_000_000, 30, 690, 90, 6, 5),
        (220_000, 15, 700, 30, 4, 2),
        (880_000, 90, 360, 60, 30, 28),
        (1_500_000, 45, 500, 45, 14, 11),
        (3_200_000, 0, 820, 60, 25, 0),
        (450_000, 120, 340, 30, 9, 8),
        (700_000, 0, 760, 30, 2, 0),
        (700_000, 1, 760, 30, 2, 1),
        (110_000, 0, 300, 90, 1, 0),
        (20_000_000, 60, 420, 90, 12, 10),
        (350_000, 30, 650, 1, 20, 5),
        (650_000, 0, 900, 120, 100, 0),
        (650_000, 50, 900, 120, 100, 40),
        (990_000, 75, 400, 60, 40, 35),
    ]
    invoice_amount, days_overdue, credit_score, payment_terms, num_prev, num_late = presets[t]

    payment_terms = max(1, payment_terms)
    num_late = min(num_late, num_prev)
    avg_days_to_pay = float(min(130.0, max(15.0, 25.0 + (700 - credit_score) * 0.08 + days_overdue * 0.15)))

    is_overdue = days_overdue > 0
    if is_overdue and random.random() < 0.55:
        customer_total_overdue = round(invoice_amount * random.uniform(1.2, 3.5), -3)
    else:
        customer_total_overdue = round(invoice_amount, -3) if is_overdue else 0.0

    delay_prob, will_be_late_in_30_days, paid_in_7, paid_in_15, paid_in_30, risk_label = _delay_prob_and_risk(
        avg_days_to_pay,
        payment_terms,
        credit_score,
        num_prev,
        num_late,
        customer_total_overdue,
        invoice_amount,
        industry_code,
        label_bias,
        noise_scale=0.04,
    )

    inv_id = f"INV-E{seq:05d}"
    cid = 10_000 + (seq % max(N_UNIQUE_CUSTOMERS, 1))

    return {
        "invoice_id": inv_id,
        "customer_id": cid,
        "invoice_amount": invoice_amount,
        "days_overdue": days_overdue,
        "customer_credit_score": credit_score,
        "customer_avg_days_to_pay": avg_days_to_pay,
        "payment_terms": payment_terms,
        "num_previous_invoices": num_prev,
        "num_late_payments": num_late,
        "industry_encoded": industry_code,
        "customer_total_overdue": customer_total_overdue,
        "paid_in_7": paid_in_7,
        "paid_in_15": paid_in_15,
        "paid_in_30": paid_in_30,
        "will_be_late_in_30_days": will_be_late_in_30_days,
        "risk_label": risk_label,
        "delay_probability_target": round(delay_prob, 6),
        "currency": "INR",
        "industry_name": ind["name"],
    }


def print_stats(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"  Dataset Summary — {len(df)} records")
    print(f"{'='*55}")

    print(f"\n  Currency: INR")
    print(f"  Invoice Amount:")
    print(f"    Min:    INR {df['invoice_amount'].min():>15,.0f}")
    print(f"    Max:    INR {df['invoice_amount'].max():>15,.0f}")
    print(f"    Median: INR {df['invoice_amount'].median():>15,.0f}")
    print(f"    Mean:   INR {df['invoice_amount'].mean():>15,.0f}")

    print(f"\n  Credit Score (CIBIL):")
    print(f"    Min:  {df['customer_credit_score'].min()}")
    print(f"    Max:  {df['customer_credit_score'].max()}")
    print(f"    Mean: {df['customer_credit_score'].mean():.0f}")

    print(f"\n  Days Overdue:")
    print(f"    Overdue invoices: {(df['days_overdue'] > 0).sum()} ({(df['days_overdue'] > 0).mean():.1%})")
    print(f"    Mean DPD (when overdue): {df[df['days_overdue']>0]['days_overdue'].mean():.1f} days")

    print(f"\n  Risk Label Distribution:")
    counts = df["risk_label"].value_counts().sort_index()
    labels = {0: "Low", 1: "Medium", 2: "High"}
    for k, v in counts.items():
        bar = "#" * int(v / len(df) * 40)
        print(f"    {labels[k]:8s} ({k}): {v:4d}  {v/len(df):5.1%}  {bar}")

    print(f"\n  Payment Labels (% paid):")
    print(f"    Within 7 days:  {df['paid_in_7'].mean():.1%}")
    print(f"    Within 15 days: {df['paid_in_15'].mean():.1%}")
    print(f"    Within 30 days: {df['paid_in_30'].mean():.1%}")

    print(f"\n  Industry Breakdown:")
    for code, ind in INDUSTRIES.items():
        count = (df["industry_encoded"] == code).sum()
        print(f"    {ind['name']:20s}: {count:4d} ({count/len(df):.1%})")

    print(f"\n  Unique Customers: {df['customer_id'].nunique()}")
    print(f"{'='*55}\n")


def main():
    print(
        f"Generating INR invoices: {N_RECORDS} random + {EDGE_RECORDS} edge rows "
        f"({N_UNIQUE_CUSTOMERS} customer buckets)..."
    )
    records = [generate_record(i + 1) for i in range(N_RECORDS)]
    records.extend([generate_edge_record(i + 1) for i in range(EDGE_RECORDS)])
    df = pd.DataFrame(records)

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Rows: {len(df)}  |  Columns: {len(df.columns)}")
    print_stats(df)


if __name__ == "__main__":
    main()
