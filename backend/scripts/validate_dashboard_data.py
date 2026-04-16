"""
Cross-check dashboard data consistency (DB vs API).

Usage:
  python backend/scripts/validate_dashboard_data.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date
from dataclasses import dataclass
from typing import Any


API_BASE = "http://localhost:8000"
PSQL_CMD = [
    "docker",
    "compose",
    "exec",
    "-T",
    "postgres",
    "psql",
    "-U",
    "postgres",
    "-d",
    "ai_collector",
    "-A",
    "-t",
    "-F",
    "|",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def fetch_json(path: str) -> Any:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def psql_rows(sql: str) -> list[list[str]]:
    cmd = PSQL_CMD + ["-c", sql]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"psql command failed\nSQL: {sql}\nSTDERR:\n{proc.stderr.strip()}\nSTDOUT:\n{proc.stdout.strip()}"
        )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return [line.split("|") for line in lines]


def psql_scalar(sql: str) -> str:
    rows = psql_rows(sql)
    if not rows:
        return ""
    return rows[0][0]


def to_float(val: Any) -> float:
    try:
        return float(val)
    except Exception:
        return 0.0


def to_int(val: Any) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


def close_enough(a: float, b: float, eps: float = 0.01) -> bool:
    return abs(a - b) <= eps


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _percentile(nums: list[float], q: float) -> float:
    if not nums:
        return 1.0
    vals = sorted(nums)
    if len(vals) == 1:
        return vals[0]
    q = _clamp(q)
    pos = (len(vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def _risk_tier(days_overdue: int, amount: float, amount_ref: float) -> str:
    dpd_component = _clamp(days_overdue / 90.0)
    amount_component = _clamp(amount / max(amount_ref, 1.0))
    score = _clamp((dpd_component + amount_component) / 2.0)
    if score >= 0.67:
        return "High"
    if score >= 0.40:
        return "Medium"
    return "Low"


def run_checks() -> list[CheckResult]:
    checks: list[CheckResult] = []

    summary_rows = psql_rows(
        """
        SELECT
          COALESCE(outstanding_amount, amount) AS amount,
          status,
          due_date,
          days_overdue
        FROM invoices
        WHERE status IN ('open', 'overdue');
        """
    )
    api_summary = fetch_json("/invoices/summary")
    db_total_invoices = len(summary_rows)
    db_total_outstanding = sum(to_float(r[0]) for r in summary_rows)
    today = date.today().isoformat()
    db_overdue_amount = sum(
        to_float(r[0])
        for r in summary_rows
        if (r[1] == "overdue") or (r[1] == "open" and r[2] and r[2] < today)
    )
    db_overdue_count = sum(
        1
        for r in summary_rows
        if (r[1] == "overdue") or (r[1] == "open" and r[2] and r[2] < today)
    )
    amounts = [to_float(r[0]) for r in summary_rows]
    amount_ref = max(_percentile(amounts, 0.90), 1.0)
    db_risk_breakdown = {"High": 0, "Medium": 0, "Low": 0}
    db_amount_at_risk = 0.0
    for r in summary_rows:
        amt = to_float(r[0])
        tier = _risk_tier(to_int(r[3]), amt, amount_ref)
        db_risk_breakdown[tier] += 1
        if tier == "High":
            db_amount_at_risk += amt

    checks.append(
        CheckResult(
            name="Summary.total_invoices",
            ok=db_total_invoices == to_int(api_summary.get("total_invoices")),
            detail=f"db={db_total_invoices}, api={api_summary.get('total_invoices')}",
        )
    )
    checks.append(
        CheckResult(
            name="Summary.total_outstanding",
            ok=close_enough(db_total_outstanding, to_float(api_summary.get("total_outstanding"))),
            detail=f"db={db_total_outstanding:.2f}, api={to_float(api_summary.get('total_outstanding')):.2f}",
        )
    )
    checks.append(
        CheckResult(
            name="Summary.overdue_amount",
            ok=close_enough(db_overdue_amount, to_float(api_summary.get("overdue_amount"))),
            detail=f"db={db_overdue_amount:.2f}, api={to_float(api_summary.get('overdue_amount')):.2f}",
        )
    )
    checks.append(
        CheckResult(
            name="Summary.overdue_count",
            ok=db_overdue_count == to_int(api_summary.get("overdue_count")),
            detail=f"db={db_overdue_count}, api={api_summary.get('overdue_count')}",
        )
    )
    checks.append(
        CheckResult(
            name="Summary.amount_at_risk",
            ok=close_enough(db_amount_at_risk, to_float(api_summary.get("amount_at_risk"))),
            detail=f"db={db_amount_at_risk:.2f}, api={to_float(api_summary.get('amount_at_risk')):.2f}",
        )
    )
    checks.append(
        CheckResult(
            name="Summary.high_risk_count",
            ok=db_risk_breakdown["High"] == to_int(api_summary.get("high_risk_count")),
            detail=f"db={db_risk_breakdown['High']}, api={api_summary.get('high_risk_count')}",
        )
    )
    api_risk_breakdown = api_summary.get("risk_breakdown") or {}
    checks.append(
        CheckResult(
            name="Summary.risk_breakdown",
            ok=(
                db_risk_breakdown["High"] == to_int(api_risk_breakdown.get("High"))
                and db_risk_breakdown["Medium"] == to_int(api_risk_breakdown.get("Medium"))
                and db_risk_breakdown["Low"] == to_int(api_risk_breakdown.get("Low"))
            ),
            detail=(
                f"db={db_risk_breakdown}, "
                f"api={{'High': {api_risk_breakdown.get('High')}, "
                f"'Medium': {api_risk_breakdown.get('Medium')}, "
                f"'Low': {api_risk_breakdown.get('Low')}}}"
            ),
        )
    )

    db_invoice_rows = psql_rows(
        """
        SELECT invoice_number, customer_id
        FROM invoices
        WHERE status IN ('open', 'overdue')
        ORDER BY days_overdue DESC, due_date ASC;
        """
    )
    db_invoice_ids = {row[0] for row in db_invoice_rows}
    db_customer_ids = {str(row[1]) for row in db_invoice_rows}

    api_worklist = fetch_json("/prioritize/invoices")
    missing_worklist_ids = [x.get("invoice_id") for x in api_worklist if str(x.get("invoice_id")) not in db_invoice_ids]
    checks.append(
        CheckResult(
            name="Worklist.invoice_ids_exist_in_db",
            ok=len(missing_worklist_ids) == 0,
            detail="missing=" + (", ".join(missing_worklist_ids[:5]) if missing_worklist_ids else "none"),
        )
    )

    if db_invoice_rows:
        sample_invoice_id = db_invoice_rows[0][0]
        detail = fetch_json(f"/invoices/{sample_invoice_id}")
        checks.append(
            CheckResult(
                name="InvoiceDetail.sample_invoice_resolves",
                ok=str(detail.get("invoice_id")) == str(sample_invoice_id),
                detail=f"requested={sample_invoice_id}, api={detail.get('invoice_id')}",
            )
        )

    borrower_portfolio = fetch_json("/predict/borrowers/portfolio")
    missing_borrowers = [
        str(row.get("customer_id"))
        for row in borrower_portfolio
        if str(row.get("customer_id")) not in db_customer_ids
    ]
    checks.append(
        CheckResult(
            name="BorrowerPortfolio.customer_ids_exist_in_db_open_set",
            ok=len(missing_borrowers) == 0,
            detail="missing=" + (", ".join(missing_borrowers[:5]) if missing_borrowers else "none"),
        )
    )

    watchlist = fetch_json("/sentinel/watchlist")
    customers = watchlist.get("customers", []) or []
    checks.append(
        CheckResult(
            name="Watchlist.total_flagged_matches_length",
            ok=to_int(watchlist.get("total_flagged")) == len(customers),
            detail=f"total_flagged={watchlist.get('total_flagged')}, len={len(customers)}",
        )
    )

    invalid_primary_invoice_ids: list[str] = []
    for c in customers:
        inv_id = c.get("primary_invoice_id")
        if inv_id and str(inv_id) not in db_invoice_ids:
            invalid_primary_invoice_ids.append(str(inv_id))
    checks.append(
        CheckResult(
            name="Watchlist.primary_invoice_ids_exist_in_db",
            ok=len(invalid_primary_invoice_ids) == 0,
            detail="invalid=" + (", ".join(invalid_primary_invoice_ids[:5]) if invalid_primary_invoice_ids else "none"),
        )
    )

    return checks


def main() -> int:
    try:
        checks = run_checks()
    except urllib.error.URLError as exc:
        print(f"ERROR: Could not reach backend API at {API_BASE}: {exc}")
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2

    print("Dashboard Data Validation")
    print("-" * 80)
    passed = 0
    failed = 0

    for c in checks:
        status = "PASS" if c.ok else "FAIL"
        print(f"[{status}] {c.name}: {c.detail}")
        if c.ok:
            passed += 1
        else:
            failed += 1

    print("-" * 80)
    print(f"Result: {passed} passed, {failed} failed, total {len(checks)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
