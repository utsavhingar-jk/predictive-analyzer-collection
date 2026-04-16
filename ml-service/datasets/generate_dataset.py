"""
Dataset Generator — AI Collector (INR, Indian B2B Lending)

Generates 1,500 realistic invoice records for training XGBoost (payment predictor)
and LightGBM (risk classifier).

Key design decisions:
  - Amounts in INR (₹25,000 to ₹50,00,000)
  - CIBIL credit score range (300–900)
  - Indian industries with realistic payment behavior profiles
  - Labels are derived from features with calibrated noise so models learn real patterns
  - Class balance enforced: ~30% High, ~40% Medium, ~30% Low risk

Output: invoices.csv (replaces the existing 100-record file)
"""

import random
import numpy as np
import pandas as pd
from pathlib import Path

random.seed(42)
np.random.seed(42)

OUTPUT_PATH = Path(__file__).parent / "invoices.csv"
N_RECORDS = 1500

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

    # ── Days overdue ──────────────────────────────────────────────────────────
    # Higher archetype bias → more likely to be overdue and by more days
    overdue_prob = 0.15 + label_bias * 0.5 + ind["delay_bias"]
    overdue_prob = max(0.05, min(0.95, overdue_prob))

    is_overdue = random.random() < overdue_prob
    if is_overdue:
        # Overdue days correlated with payment behavior
        max_overdue = int(90 + label_bias * 120)
        days_overdue = random.randint(1, max(1, max_overdue))
    else:
        days_overdue = 0

    # ── Customer total overdue (across all their invoices) ────────────────────
    if is_overdue and random.random() < 0.6:
        # Customer likely has more overdue invoices
        multiplier = random.uniform(1.0, 4.0)
        customer_total_overdue = round(invoice_amount * multiplier, -3)
    else:
        customer_total_overdue = invoice_amount if is_overdue else 0

    # ── Compute delay probability score (0–1) ─────────────────────────────────
    # This is the core signal that drives label generation
    base_delay_prob = (
        (days_overdue / max(payment_terms, 1)) * 0.35
        + (1 - credit_score / 900) * 0.25
        + (num_late / max(num_prev, 1)) * 0.20
        + (customer_total_overdue / max(invoice_amount * 5, 1)) * 0.10
        + ind["delay_bias"] * 0.10
        + label_bias * 0.15
    )
    # Add calibrated noise
    noise = np.random.normal(0, 0.06)
    delay_prob = float(np.clip(base_delay_prob + noise, 0.01, 0.99))

    # ── Payment probability labels (what XGBoost is trained to predict) ───────
    # paid_in_7: high only if very low delay prob and not overdue much
    p7  = max(0.0, 0.95 - delay_prob * 2.2 - days_overdue * 0.02)
    p15 = max(0.0, 0.90 - delay_prob * 1.5 - days_overdue * 0.01)
    p30 = max(0.0, 0.85 - delay_prob * 0.90)
    p7, p15, p30 = min(p7, 0.98), min(p15, 0.98), min(p30, 0.98)

    paid_in_7  = int(random.random() < p7)
    paid_in_15 = int(random.random() < p15)
    paid_in_30 = int(random.random() < p30)

    # Enforce monotonicity: if paid in 7 → paid in 15 and 30
    if paid_in_7:
        paid_in_15 = 1
        paid_in_30 = 1
    if paid_in_15:
        paid_in_30 = 1

    # ── Risk label (what LightGBM is trained to predict) ──────────────────────
    # 0=Low, 1=Medium, 2=High — thresholds tuned for balanced distribution
    if delay_prob >= 0.55:
        risk_label = 2   # High
    elif delay_prob >= 0.28:
        risk_label = 1   # Medium
    else:
        risk_label = 0   # Low

    # Add slight label noise (5%) to simulate real-world imperfection
    if random.random() < 0.05:
        risk_label = random.randint(0, 2)

    return {
        "invoice_id":               f"INV-{i:05d}",
        "customer_id":              100 + (i % 300),   # 300 unique customers
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
        "risk_label":              risk_label,
        # Extra context columns (used in behavior engine but not in ML features)
        "currency":                "INR",
        "industry_name":           ind["name"],
    }


def print_stats(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"  Dataset Summary — {len(df)} records")
    print(f"{'='*55}")

    print(f"\n  Currency: INR (₹)")
    print(f"  Invoice Amount:")
    print(f"    Min:    ₹{df['invoice_amount'].min():>15,.0f}")
    print(f"    Max:    ₹{df['invoice_amount'].max():>15,.0f}")
    print(f"    Median: ₹{df['invoice_amount'].median():>15,.0f}")
    print(f"    Mean:   ₹{df['invoice_amount'].mean():>15,.0f}")

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
        bar = "█" * int(v / len(df) * 40)
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
    print("Generating 1,500-record INR dataset for AI Collector ML training...")
    records = [generate_record(i + 1) for i in range(N_RECORDS)]
    df = pd.DataFrame(records)

    # Print stats before saving
    print_stats(df)

    # Save — drop display-only columns that aren't model features
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved: {OUTPUT_PATH}")
    print(f"Rows: {len(df)}  |  Columns: {len(df.columns)}")


if __name__ == "__main__":
    main()
