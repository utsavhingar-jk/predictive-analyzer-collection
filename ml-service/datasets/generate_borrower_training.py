"""
Build datasets/borrower_training.csv from invoices.csv + synthetic edge borrowers.

Uses the same aggregation + target as training/train_borrower.py.
Run after: python datasets/generate_dataset.py
"""

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.train_borrower import FEATURE_COLS, aggregate_invoices

OUTPUT_PATH = Path(__file__).parent / "borrower_training.csv"
INVOICES_PATH = Path(__file__).parent / "invoices.csv"


def borrower_heuristic_score(
    wdp: float,
    overdue_ratio: float,
    credit_score: float,
    num_late: int,
    conc: float,
) -> float:
    credit_factor = max(0.0, (700 - credit_score) / 400)
    late_factor = min(1.0, num_late / 10)
    score_raw = (
        wdp * 0.40
        + overdue_ratio * 0.20
        + credit_factor * 0.20
        + late_factor * 0.10
        + conc * 0.10
    )
    return float(min(100, round(score_raw * 100)))


def synthetic_borrower_edge_rows() -> pd.DataFrame:
    """Explicit edge combinations for borrower XGBoost (grid product of listed values)."""
    rows = []
    credits = [300, 400, 520, 600, 680, 750, 850, 900]
    wdps = [0.02, 0.12, 0.28, 0.52, 0.72, 0.92]
    ov_ratios = [0.0, 0.08, 0.25, 0.55, 0.92, 1.0]
    lates = [0, 2, 6, 11]
    open_cs = [1, 3, 12, 45]

    for credit, wdp, ov_ratio, late, open_c in itertools.product(
        credits, wdps, ov_ratios, lates, open_cs
    ):
        overdue_c = min(open_c, max(0, int(round(open_c * ov_ratio))))
        # Deterministic portfolio spread (matches aggregate when single-borrower bucket)
        per_open = 95_000.0 + (credit % 50) * 800.0
        portfolio = max(25_000.0, float(open_c) * per_open)
        total_out = portfolio
        conc = min(1.0, (total_out / max(portfolio, 1.0)) / 0.5)
        heur = borrower_heuristic_score(wdp, ov_ratio, credit, late, conc)
        risk_approx = min(2.0, max(0.0, wdp * 1.8 + ov_ratio * 0.8))
        y = 0.42 * heur + 0.32 * (risk_approx / 2.0 * 100.0) + 0.26 * (wdp * 100.0)
        y = float(max(0.0, min(100.0, round(y))))
        rows.append({
            "credit_score": float(credit),
            "avg_days_to_pay": float(min(120.0, max(18.0, 28.0 + (850 - credit) * 0.12))),
            "payment_terms": 30.0,
            "num_late_payments": int(late),
            "portfolio_total_outstanding": portfolio,
            "total_outstanding": total_out,
            "open_invoice_count": int(open_c),
            "overdue_invoice_count": int(overdue_c),
            "weighted_delay_probability": round(wdp, 4),
            "overdue_ratio": round(ov_ratio, 4),
            "borrower_risk_score_target": y,
        })
    return pd.DataFrame(rows)


def main() -> None:
    if not INVOICES_PATH.is_file():
        raise SystemExit(f"Missing {INVOICES_PATH} — run: python datasets/generate_dataset.py")

    inv = pd.read_csv(INVOICES_PATH)
    agg = aggregate_invoices(inv)
    edges = synthetic_borrower_edge_rows()

    combined = pd.concat([agg, edges], ignore_index=True)
    combined["log_portfolio"] = np.log1p(combined["portfolio_total_outstanding"].clip(lower=0))

    out_cols = FEATURE_COLS + ["borrower_risk_score_target"]
    combined[out_cols].to_csv(OUTPUT_PATH, index=False)
    print(
        f"Saved {len(combined)} rows ({len(agg)} from invoice aggregates + {len(edges)} edge) -> {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
