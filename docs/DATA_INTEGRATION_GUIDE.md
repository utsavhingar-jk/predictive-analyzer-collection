# Data Integration Guide — Connecting Your Existing Dataset

> This guide tells you exactly which tables/columns to pull from your existing database,
> how to compute missing fields from raw data, and how to replace the mock data layer
> step by step.

---

## Table of Contents

1. [What Data the System Needs — Master Checklist](#1-what-data-the-system-needs--master-checklist)
2. [Source Table Map — What to Pick From Your DB](#2-source-table-map--what-to-pick-from-your-db)
3. [Computed Fields — Fields You Derive, Not Store](#3-computed-fields--fields-you-derive-not-store)
4. [Minimum Viable Dataset (MVP)](#4-minimum-viable-dataset-mvp)
5. [Full Field Mapping Table](#5-full-field-mapping-table)
6. [SQL Queries to Build the Integration View](#6-sql-queries-to-build-the-integration-view)
7. [How to Replace mock_data.py Step by Step](#7-how-to-replace-mock_datapy-step-by-step)
8. [Payment History → Behavior Signals (Most Important)](#8-payment-history--behavior-signals-most-important)
9. [What to Do When Fields Are Missing](#9-what-to-do-when-fields-are-missing)
10. [Data Quality Checklist Before Going Live](#10-data-quality-checklist-before-going-live)

---

## 1. What Data the System Needs — Master Checklist

The system has **3 data domains**. Each domain comes from different source tables in a typical lending/ERP system.

### Domain A — Invoice / Loan Data
Everything about the current open receivable.

```
✅ REQUIRED (system breaks without these)
  - invoice_id / loan_id           unique identifier
  - customer_id / borrower_id      link to the customer
  - invoice_amount / loan_amount   outstanding principal
  - issue_date                     when invoice was raised
  - due_date                       when payment is expected
  - payment_terms                  30 / 60 / 90 days
  - status                         open / overdue / paid
  - currency                       USD / INR / etc.

⚠️  NEEDED (calculated from above if missing)
  - days_overdue                   computed: today - due_date (if past due)

📊 NICE TO HAVE (improves ML accuracy)
  - invoice_number                 human-readable ID
  - industry / sector              borrower's industry
  - invoice_type                   trade / service / loan EMI
```

### Domain B — Customer / Borrower Master Data
Who the borrower is and their creditworthiness signals.

```
✅ REQUIRED
  - customer_id                    primary key
  - customer_name / company_name   display name

⚠️  NEEDED
  - credit_score                   300–850 range (CIBIL / internal rating)
  - payment_terms                  standard terms for this customer

📊 NICE TO HAVE (high impact on predictions)
  - industry / sector
  - borrower_type                  corporate / SME / individual
  - registration_number            GST / CIN / PAN
```

### Domain C — Payment Transaction History
This is the most important data source. It powers the entire Behavior Engine.

```
✅ REQUIRED (for behavior analysis)
  - customer_id                    link to borrower
  - invoice_id                     which invoice was paid
  - amount_paid                    how much was paid
  - payment_date                   when payment was received
  - due_date (of that invoice)     to compute actual delay

📊 NICE TO HAVE
  - payment_mode                   NACH / NEFT / cheque / UPI
  - payment_status                 success / failed / bounced
  - bounce_count                   number of failed attempts
  - followup_count                 how many reminders before payment
  - partial_flag                   was this a partial payment
```

---

## 2. Source Table Map — What to Pick From Your DB

Most lending/ERP systems have these tables under different names.
Match the concept to your table name:

| System Concept | Typical Table Names in Your DB |
|---|---|
| **Invoice / Loan Ledger** | `invoices`, `loans`, `loan_accounts`, `dues`, `demands`, `repayment_schedule`, `emi_schedule` |
| **Customer / Borrower Master** | `customers`, `borrowers`, `clients`, `accounts`, `parties`, `members` |
| **Payment History** | `payments`, `transactions`, `receipts`, `collections`, `repayments`, `payment_log` |
| **Credit Profile** | `credit_bureau`, `cibil_data`, `credit_scores`, `risk_ratings`, `customer_profile` |
| **Collection Activity** | `collection_activities`, `followup_log`, `calls_log`, `field_visits` |

---

## 3. Computed Fields — Fields You Derive, Not Store

Several fields the system needs **do not exist in your DB** — they are computed from raw history.
Here is exactly how to compute each one:

### `days_overdue`
```sql
-- Compute on the fly from due_date
GREATEST(0, CURRENT_DATE - due_date) AS days_overdue

-- Status
CASE
  WHEN paid_date IS NOT NULL           THEN 'paid'
  WHEN CURRENT_DATE > due_date         THEN 'overdue'
  ELSE                                      'open'
END AS status
```

### `avg_days_to_pay` (per customer)
```sql
-- Average actual payment delay across all historical invoices
SELECT
    customer_id,
    AVG(
        EXTRACT(DAY FROM (p.payment_date - i.due_date))
    ) AS avg_days_to_pay
FROM payments p
JOIN invoices i ON i.id = p.invoice_id
WHERE p.payment_status = 'success'
GROUP BY customer_id
```

### `num_late_payments` (per customer)
```sql
-- Count of invoices where payment came AFTER due date
SELECT
    i.customer_id,
    COUNT(*) AS num_late_payments
FROM payments p
JOIN invoices i ON i.id = p.invoice_id
WHERE p.payment_date > i.due_date
  AND p.payment_status = 'success'
GROUP BY i.customer_id
```

### `customer_total_overdue` (per customer, live)
```sql
-- Sum of all currently overdue amounts for this customer
SELECT
    customer_id,
    SUM(amount) AS customer_total_overdue
FROM invoices
WHERE status = 'overdue'
  OR (CURRENT_DATE > due_date AND paid_date IS NULL)
GROUP BY customer_id
```

### `historical_on_time_ratio` (for Behavior Engine)
```sql
-- Fraction of invoices paid on or before due date
SELECT
    i.customer_id,
    ROUND(
        COUNT(*) FILTER (WHERE p.payment_date <= i.due_date)::numeric
        / NULLIF(COUNT(*), 0),
        4
    ) AS on_time_ratio
FROM invoices i
JOIN payments p ON p.invoice_id = i.id
WHERE p.payment_status = 'success'
GROUP BY i.customer_id
```

### `deterioration_trend` (for Behavior Engine)
```sql
-- Compare avg delay in last 3 months vs prior 3 months
-- Positive = getting worse, Negative = improving
WITH recent AS (
    SELECT i.customer_id,
           AVG(EXTRACT(DAY FROM (p.payment_date - i.due_date))) AS avg_delay
    FROM payments p JOIN invoices i ON i.id = p.invoice_id
    WHERE p.payment_date >= NOW() - INTERVAL '3 months'
      AND p.payment_status = 'success'
    GROUP BY i.customer_id
),
prior AS (
    SELECT i.customer_id,
           AVG(EXTRACT(DAY FROM (p.payment_date - i.due_date))) AS avg_delay
    FROM payments p JOIN invoices i ON i.id = p.invoice_id
    WHERE p.payment_date BETWEEN NOW() - INTERVAL '6 months' AND NOW() - INTERVAL '3 months'
      AND p.payment_status = 'success'
    GROUP BY i.customer_id
)
SELECT r.customer_id,
       ROUND(
           LEAST(1, GREATEST(-1,
               (r.avg_delay - COALESCE(p.avg_delay, r.avg_delay)) / 30.0
           ))
       , 4) AS deterioration_trend
FROM recent r
LEFT JOIN prior p ON p.customer_id = r.customer_id
```

### `partial_payment_frequency` (for Behavior Engine)
```sql
-- How often they pay less than the full invoice amount
SELECT
    i.customer_id,
    ROUND(
        COUNT(*) FILTER (WHERE p.amount_paid < i.amount)::numeric
        / NULLIF(COUNT(*), 0),
        4
    ) AS partial_payment_frequency
FROM invoices i
JOIN payments p ON p.invoice_id = i.id
WHERE p.payment_status = 'success'
GROUP BY i.customer_id
```

### `payment_after_followup_count` (for Behavior Engine)
```sql
-- Number of invoices paid only after a collection followup was logged
-- Assumes you have a followup_log or collection_activities table
SELECT
    i.customer_id,
    COUNT(DISTINCT i.id) AS payment_after_followup_count
FROM invoices i
JOIN payments p ON p.invoice_id = i.id
JOIN followup_log f ON f.invoice_id = i.id
    AND f.followup_date < p.payment_date   -- followup happened before payment
WHERE p.payment_status = 'success'
GROUP BY i.customer_id
```

### `bounce_rate` / `transaction_success_failure_pattern`
```sql
-- Ratio of failed/bounced payment attempts
SELECT
    i.customer_id,
    ROUND(
        COUNT(*) FILTER (WHERE p.payment_status IN ('failed', 'bounced'))::numeric
        / NULLIF(COUNT(*), 0),
        4
    ) AS transaction_failure_rate
FROM payments p
JOIN invoices i ON i.id = p.invoice_id
GROUP BY i.customer_id
```

---

## 4. Minimum Viable Dataset (MVP)

If your data is heavily segregated and you can only pull a few things, here is the **minimum** that makes the system work end-to-end:

### Table 1 — `invoices_view` (JOIN of your invoice + customer tables)
```
Column                  Source              Priority
──────────────────────────────────────────────────────
invoice_id              your invoice table  REQUIRED
customer_id             your invoice table  REQUIRED
customer_name           your customer table REQUIRED
amount                  your invoice table  REQUIRED
issue_date              your invoice table  REQUIRED
due_date                your invoice table  REQUIRED
payment_terms           your invoice table  REQUIRED
status                  computed (see §3)   REQUIRED
days_overdue            computed (see §3)   REQUIRED
credit_score            credit bureau / internal  NEEDED
avg_days_to_pay         computed from history     NEEDED
num_late_payments       computed from history     NEEDED
customer_total_overdue  computed from history     NEEDED
industry                customer master     NICE TO HAVE
currency                invoice table       NICE TO HAVE
```

### Table 2 — `payment_history_view`
```
Column          Source                  Priority
─────────────────────────────────────────────────
customer_id     payments/transactions   REQUIRED
payment_date    payments/transactions   REQUIRED
amount_paid     payments/transactions   REQUIRED
due_date        linked invoice          REQUIRED
payment_status  payments/transactions   REQUIRED
invoice_id      payments/transactions   NEEDED
partial_flag    computed or stored      NICE TO HAVE
bounce_count    payments/transactions   NICE TO HAVE
followup_count  collection log          NICE TO HAVE
```

---

## 5. Full Field Mapping Table

Map every field the system reads to your actual column name:

| System Field | Used In | Your Table | Your Column | Fallback if Missing |
|---|---|---|---|---|
| `invoice_id` | All | `invoices` | ? | Required — no fallback |
| `customer_id` | All | `invoices` | ? | Required — no fallback |
| `customer_name` | All | `customers` | ? | Required — no fallback |
| `amount` | All | `invoices` | ? | Required — no fallback |
| `issue_date` | Invoice card | `invoices` | ? | Use `due_date - payment_terms` |
| `due_date` | All | `invoices` | ? | Required — no fallback |
| `payment_terms` | Delay model | `invoices` | ? | Default to 30 |
| `status` | All | Computed | — | Compute from `due_date` |
| `days_overdue` | All | Computed | — | `max(0, today - due_date)` |
| `credit_score` | Delay model | `customers` / bureau | ? | Default to 650 |
| `avg_days_to_pay` | All pillars | Computed | — | Compute from payment history |
| `num_late_payments` | Delay model | Computed | — | Count from history |
| `customer_total_overdue` | Borrower | Computed | — | Sum overdue per customer |
| `industry` | Display / agent | `customers` | ? | Default to "unknown" |
| `currency` | Display | `invoices` | ? | Default to "INR" |
| `pay_7_days` | Dashboard | ML prediction | — | Rule: `max(0, 0.7 - delay_prob)` |
| `pay_15_days` | Invoice detail | ML prediction | — | Rule: `max(0, 0.85 - delay_prob)` |
| `pay_30_days` | All forecasts | ML prediction | — | Rule: `1 - delay_probability` |
| `risk_label` | Worklist | ML prediction | — | Derived from `delay_probability` |
| `historical_on_time_ratio` | Behavior | Computed | — | Compute from payment history |
| `avg_delay_days` | Behavior | Computed | — | Compute from payment history |
| `deterioration_trend` | Behavior | Computed | — | Compute from payment history |
| `partial_payment_frequency` | Behavior | Computed | — | Compute from payment history |
| `payment_after_followup_count` | Behavior | Computed | — | Compute from followup log |
| `transaction_success_failure_pattern` | Behavior | Computed | — | Compute from bounce records |

---

## 6. SQL Queries to Build the Integration View

### Step A — Customer Behavior Summary View

Run this once (or nightly) to pre-compute all behavior signals per customer:

```sql
CREATE OR REPLACE VIEW v_customer_behavior_signals AS

WITH payment_stats AS (
    SELECT
        i.customer_id,
        COUNT(*)                                                         AS total_invoices,
        COUNT(*) FILTER (WHERE p.payment_date <= i.due_date)            AS on_time_count,
        AVG(GREATEST(0, EXTRACT(DAY FROM (p.payment_date - i.due_date)))) AS avg_delay_days,
        STDDEV(EXTRACT(DAY FROM (p.payment_date - i.due_date)))          AS delay_stddev,
        COUNT(*) FILTER (WHERE p.amount_paid < i.amount * 0.99)         AS partial_count,
        SUM(CASE WHEN p.payment_status IN ('failed','bounced') THEN 1 ELSE 0 END)
                                                                         AS bounce_count,
        COUNT(*)                                                         AS total_attempts
    FROM invoices i
    JOIN payments p ON p.invoice_id = i.id
    GROUP BY i.customer_id
),
recent_delay AS (
    SELECT i.customer_id,
           AVG(EXTRACT(DAY FROM (p.payment_date - i.due_date))) AS recent_avg_delay
    FROM payments p JOIN invoices i ON i.id = p.invoice_id
    WHERE p.payment_date >= NOW() - INTERVAL '90 days'
    GROUP BY i.customer_id
),
prior_delay AS (
    SELECT i.customer_id,
           AVG(EXTRACT(DAY FROM (p.payment_date - i.due_date))) AS prior_avg_delay
    FROM payments p JOIN invoices i ON i.id = p.invoice_id
    WHERE p.payment_date BETWEEN NOW() - INTERVAL '180 days' AND NOW() - INTERVAL '90 days'
    GROUP BY i.customer_id
)

SELECT
    ps.customer_id,
    ps.total_invoices,

    -- On-time ratio (0 to 1)
    ROUND(ps.on_time_count::numeric / NULLIF(ps.total_invoices, 0), 4)
        AS historical_on_time_ratio,

    -- Average delay days
    ROUND(COALESCE(ps.avg_delay_days, 0), 1)
        AS avg_delay_days,

    -- Repayment consistency: lower stddev = more consistent
    ROUND(GREATEST(0, 1 - COALESCE(ps.delay_stddev, 0) / 30.0), 4)
        AS repayment_consistency,

    -- Partial payment frequency (0 to 1)
    ROUND(ps.partial_count::numeric / NULLIF(ps.total_invoices, 0), 4)
        AS partial_payment_frequency,

    -- Prior delayed invoice count (raw)
    ps.total_invoices - ps.on_time_count
        AS prior_delayed_invoice_count,

    -- Transaction failure rate (0 to 1)
    ROUND(ps.bounce_count::numeric / NULLIF(ps.total_attempts, 0), 4)
        AS transaction_success_failure_pattern,

    -- Deterioration trend: +1 = worsening, -1 = improving
    ROUND(
        LEAST(1, GREATEST(-1,
            COALESCE(
                (rd.recent_avg_delay - pd.prior_avg_delay) / 30.0,
                0
            )
        )),
        4
    ) AS deterioration_trend

FROM payment_stats ps
LEFT JOIN recent_delay rd ON rd.customer_id = ps.customer_id
LEFT JOIN prior_delay  pd ON pd.customer_id = ps.customer_id;
```

---

### Step B — Invoice Portfolio View (feeds the worklist + dashboard)

```sql
CREATE OR REPLACE VIEW v_invoice_portfolio AS

SELECT
    -- Invoice identity
    i.id                                                    AS invoice_id,
    i.invoice_number,
    i.customer_id,
    c.name                                                  AS customer_name,
    COALESCE(c.industry, 'unknown')                         AS industry,

    -- Amounts
    i.amount,
    COALESCE(i.currency, 'INR')                             AS currency,

    -- Dates
    i.issue_date,
    i.due_date,
    COALESCE(i.payment_terms, 30)                           AS payment_terms,

    -- Computed status
    CASE
        WHEN i.paid_date IS NOT NULL                        THEN 'paid'
        WHEN CURRENT_DATE > i.due_date                      THEN 'overdue'
        ELSE                                                     'open'
    END                                                     AS status,

    -- Days overdue (0 if not yet due)
    GREATEST(0, CURRENT_DATE - i.due_date)                  AS days_overdue,

    -- Customer risk signals
    COALESCE(c.credit_score, 650)                           AS credit_score,
    COALESCE(bh.avg_days_to_pay, 30)                        AS avg_days_to_pay,
    COALESCE(bh.num_late_payments, 0)                       AS num_late_payments,

    -- Customer total overdue (across ALL their invoices)
    COALESCE(cto.customer_total_overdue, 0)                 AS customer_total_overdue,

    -- Behavior signals (from v_customer_behavior_signals)
    COALESCE(bs.historical_on_time_ratio, 0.7)              AS historical_on_time_ratio,
    COALESCE(bs.avg_delay_days, 10)                         AS avg_delay_days_historical,
    COALESCE(bs.repayment_consistency, 0.6)                 AS repayment_consistency,
    COALESCE(bs.partial_payment_frequency, 0.1)             AS partial_payment_frequency,
    COALESCE(bs.prior_delayed_invoice_count, 0)             AS prior_delayed_invoice_count,
    COALESCE(bs.transaction_success_failure_pattern, 0.05)  AS transaction_failure_rate,
    COALESCE(bs.deterioration_trend, 0)                     AS deterioration_trend,
    bs.total_invoices

FROM invoices i
JOIN customers c ON c.id = i.customer_id

-- Pre-computed avg_days_to_pay and num_late_payments per customer
LEFT JOIN (
    SELECT
        i2.customer_id,
        ROUND(AVG(GREATEST(0, EXTRACT(DAY FROM (p.payment_date - i2.due_date)))), 1)
                                                            AS avg_days_to_pay,
        COUNT(*) FILTER (WHERE p.payment_date > i2.due_date) AS num_late_payments
    FROM invoices i2
    JOIN payments p ON p.invoice_id = i2.id
    WHERE p.payment_status = 'success'
    GROUP BY i2.customer_id
) bh ON bh.customer_id = i.customer_id

-- Customer total overdue
LEFT JOIN (
    SELECT customer_id, SUM(amount) AS customer_total_overdue
    FROM invoices
    WHERE CURRENT_DATE > due_date AND paid_date IS NULL
    GROUP BY customer_id
) cto ON cto.customer_id = i.customer_id

-- Behavior signals
LEFT JOIN v_customer_behavior_signals bs ON bs.customer_id = i.customer_id

WHERE i.paid_date IS NULL   -- only open / overdue invoices
ORDER BY GREATEST(0, CURRENT_DATE - i.due_date) DESC;
```

---

### Step C — Quick Validation Query

After creating the view, run this to make sure the data looks right:

```sql
-- Check the view returns sensible values
SELECT
    invoice_id,
    customer_name,
    amount,
    status,
    days_overdue,
    credit_score,
    avg_days_to_pay,
    num_late_payments,
    historical_on_time_ratio,
    deterioration_trend
FROM v_invoice_portfolio
ORDER BY days_overdue DESC
LIMIT 20;

-- Check for nulls in required fields
SELECT
    COUNT(*) FILTER (WHERE customer_id IS NULL)     AS missing_customer_id,
    COUNT(*) FILTER (WHERE amount IS NULL)          AS missing_amount,
    COUNT(*) FILTER (WHERE due_date IS NULL)        AS missing_due_date,
    COUNT(*) FILTER (WHERE credit_score IS NULL)    AS missing_credit_score,
    COUNT(*) FILTER (WHERE avg_days_to_pay IS NULL) AS missing_avg_days
FROM v_invoice_portfolio;
```

---

## 7. How to Replace mock_data.py Step by Step

### Step 1 — Add DB connection to backend

`backend/app/core/database.py` already has SQLAlchemy configured.
Just set your `DATABASE_URL` in `backend/.env`:

```env
DATABASE_URL=postgresql://user:password@host:5432/your_db
```

### Step 2 — Create a `db_data.py` next to `mock_data.py`

```
backend/app/utils/
  mock_data.py      ← keep for fallback / testing
  db_data.py        ← NEW: real DB queries
```

```python
# backend/app/utils/db_data.py

from sqlalchemy import text
from app.core.database import SessionLocal


def get_invoices_from_db() -> list[dict]:
    """
    Replaces MOCK_INVOICES.
    Reads from v_invoice_portfolio — the view you created in Step B above.
    """
    with SessionLocal() as db:
        rows = db.execute(text("SELECT * FROM v_invoice_portfolio")).mappings().all()
        result = []
        for row in rows:
            inv = dict(row)
            # Serialize dates to ISO strings (JSON-serializable)
            for field in ("issue_date", "due_date"):
                if inv.get(field) and hasattr(inv[field], "isoformat"):
                    inv[field] = inv[field].isoformat()
            # Ensure status and days_overdue exist
            inv.setdefault("status", "open")
            inv.setdefault("days_overdue", 0)
            # ML predictions — set to None if not yet computed
            # (the system will compute them via the rule engine)
            inv.setdefault("pay_7_days", None)
            inv.setdefault("pay_15_days", None)
            inv.setdefault("pay_30_days", None)
            inv.setdefault("risk_label", "Medium")
            result.append(inv)
        return result


def get_invoice_by_id_from_db(invoice_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT * FROM v_invoice_portfolio WHERE invoice_id = :id"),
            {"id": invoice_id}
        ).mappings().one_or_none()
        if not row:
            return None
        inv = dict(row)
        for field in ("issue_date", "due_date"):
            if inv.get(field) and hasattr(inv[field], "isoformat"):
                inv[field] = inv[field].isoformat()
        return inv


def get_portfolio_summary_from_db() -> dict:
    with SessionLocal() as db:
        rows = db.execute(text("SELECT * FROM v_invoice_portfolio")).mappings().all()
        invoices = [dict(r) for r in rows]

    total_outstanding = sum(i["amount"] for i in invoices)
    overdue_count     = sum(1 for i in invoices if i["status"] == "overdue")
    overdue_amount    = sum(i["amount"] for i in invoices if i["status"] == "overdue")
    high_risk         = sum(1 for i in invoices if i.get("risk_label") == "High")
    medium_risk       = sum(1 for i in invoices if i.get("risk_label") == "Medium")
    low_risk          = sum(1 for i in invoices if i.get("risk_label") == "Low")
    # Amount at risk: delay_prob > 0.60 → approx where pay_30_days < 0.40
    amount_at_risk    = sum(
        i["amount"] for i in invoices
        if i.get("pay_30_days") is not None and i["pay_30_days"] < 0.40
    )
    return {
        "total_invoices":    len(invoices),
        "total_outstanding": total_outstanding,
        "overdue_count":     overdue_count,
        "overdue_amount":    overdue_amount,
        "amount_at_risk":    amount_at_risk,
        "high_risk_count":   high_risk,
        "risk_breakdown":    {"High": high_risk, "Medium": medium_risk, "Low": low_risk},
    }
```

### Step 3 — Switch the import in mock_data.py (single-line change)

At the top of any service file that imports from `mock_data`, add a toggle:

```python
# backend/app/utils/mock_data.py  (add these lines at the bottom)

import os

USE_DB = os.getenv("USE_DB", "false").lower() == "true"

if USE_DB:
    from app.utils.db_data import (
        get_invoices_from_db          as _get_invoices,
        get_invoice_by_id_from_db     as get_invoice_by_id,
        get_portfolio_summary_from_db as get_portfolio_summary,
    )
    MOCK_INVOICES = _get_invoices()
```

Then in `backend/.env`, flip it on when ready:
```env
USE_DB=true
```

This lets you switch between mock and live data **without changing any service code**.

---

## 8. Payment History → Behavior Signals (Most Important)

The Behavior Engine (Pillar 1) needs these 9 signals per customer.
Here is exactly how to compute each from raw payment transaction records:

| Behavior Signal | Computation | SQL Column |
|---|---|---|
| `historical_on_time_ratio` | paid_on_time / total_payments | `on_time_count / total_invoices` |
| `avg_delay_days` | avg(payment_date - due_date) where late | `avg_delay_days` |
| `repayment_consistency` | 1 - stddev(delay_days)/30 | `repayment_consistency` |
| `partial_payment_frequency` | partial_payments / total_payments | `partial_count / total_invoices` |
| `prior_delayed_invoice_count` | count of late invoices | `total - on_time_count` |
| `payment_after_followup_count` | payments preceded by followup event | Join with `followup_log` |
| `deterioration_trend` | recent avg delay vs prior avg delay | `(recent - prior) / 30` |
| `invoice_acknowledgement_behavior` | "normal" / "slow" / "disputes" | From `followup_log.response_type` |
| `transaction_success_failure_pattern` | bounce_count / total_attempts | `bounce_count / total_attempts` |

All of these are pre-computed in `v_customer_behavior_signals` (see Section 6, Step A).

---

## 9. What to Do When Fields Are Missing

Your existing data will likely be missing some fields. Here is the fallback strategy:

| Missing Field | What to Do |
|---|---|
| `credit_score` | Use internal rating (1–10 scale), normalize to 300–850 range: `300 + (rating/10 × 550)` |
| `avg_days_to_pay` | Compute from payment history. If no history: default to `payment_terms + 5` |
| `num_late_payments` | Compute from payment history. If no history: use 0 |
| `industry` | Look up from GST/registration database, or default to "unknown" |
| `payment_terms` | Default to 30. Pull from loan agreement table if available |
| `historical_on_time_ratio` | If no payment history (new customer): default to 0.7 (neutral) |
| `deterioration_trend` | If < 6 months of history: default to 0.0 (stable) |
| `partial_payment_frequency` | If no partial records: default to 0.0 |
| `payment_after_followup_count` | If no followup log: default to 0 |
| `bounce_count` | If no bounce records: default to 0 |

### For Brand-New Customers (No History)

Use these safe neutral defaults:

```python
new_customer_behavior_defaults = {
    "historical_on_time_ratio": 0.70,   # assume mostly reliable
    "avg_delay_days": 5.0,
    "repayment_consistency": 0.70,
    "partial_payment_frequency": 0.05,
    "prior_delayed_invoice_count": 0,
    "payment_after_followup_count": 0,
    "deterioration_trend": 0.0,
    "invoice_acknowledgement_behavior": "normal",
    "transaction_success_failure_pattern": 0.0,
}
```

---

## 10. Data Quality Checklist Before Going Live

Run these checks on your dataset before switching `USE_DB=true`:

```sql
-- 1. All invoices have a customer
SELECT COUNT(*) FROM invoices i
LEFT JOIN customers c ON c.id = i.customer_id
WHERE c.id IS NULL;
-- Expected: 0

-- 2. No zero or negative amounts
SELECT COUNT(*) FROM invoices WHERE amount <= 0;
-- Expected: 0

-- 3. due_date always after issue_date
SELECT COUNT(*) FROM invoices WHERE due_date <= issue_date;
-- Expected: 0

-- 4. Reasonable payment terms
SELECT COUNT(*) FROM invoices WHERE payment_terms > 365 OR payment_terms < 1;
-- Expected: 0

-- 5. Credit scores in valid range
SELECT COUNT(*) FROM customers WHERE credit_score < 300 OR credit_score > 850;
-- Normalize any out-of-range values before using

-- 6. avg_days_to_pay is positive
SELECT COUNT(*) FROM v_invoice_portfolio WHERE avg_days_to_pay < 0;
-- Expected: 0

-- 7. No duplicate invoice IDs
SELECT invoice_id, COUNT(*) FROM v_invoice_portfolio
GROUP BY invoice_id HAVING COUNT(*) > 1;
-- Expected: empty

-- 8. Behavior signals are in valid range (0–1 fractions)
SELECT COUNT(*) FROM v_customer_behavior_signals
WHERE historical_on_time_ratio > 1 OR historical_on_time_ratio < 0
   OR partial_payment_frequency > 1 OR partial_payment_frequency < 0;
-- Expected: 0
```

---

## Quick Summary — What You Need to Pull From Your DB

If you have a typical lending system with `loans`, `customers`, and `payments` tables,
here is the absolute minimum SQL to get started:

```sql
-- THE ONE QUERY THAT FEEDS EVERYTHING
SELECT
    l.id                                                 AS invoice_id,
    l.loan_number                                        AS invoice_number,
    l.customer_id,
    c.name                                               AS customer_name,
    c.industry,
    l.outstanding_amount                                 AS amount,
    l.disbursal_date                                     AS issue_date,
    l.due_date,
    COALESCE(l.repayment_tenure, 30)                     AS payment_terms,
    CASE WHEN CURRENT_DATE > l.due_date
         AND l.status != 'closed'                        THEN 'overdue'
         WHEN l.status = 'closed'                        THEN 'paid'
         ELSE                                                 'open'
    END                                                  AS status,
    GREATEST(0, CURRENT_DATE - l.due_date)               AS days_overdue,
    COALESCE(c.cibil_score, 650)                         AS credit_score,
    COALESCE(h.avg_days_to_pay, 30)                      AS avg_days_to_pay,
    COALESCE(h.num_late_payments, 0)                     AS num_late_payments,
    COALESCE(ot.customer_total_overdue, 0)               AS customer_total_overdue

FROM loans l
JOIN customers c ON c.id = l.customer_id

LEFT JOIN (
    SELECT l2.customer_id,
           AVG(EXTRACT(DAY FROM (r.payment_date - l2.due_date))) AS avg_days_to_pay,
           COUNT(*) FILTER (WHERE r.payment_date > l2.due_date)  AS num_late_payments
    FROM repayments r JOIN loans l2 ON l2.id = r.loan_id
    WHERE r.status = 'success'
    GROUP BY l2.customer_id
) h ON h.customer_id = l.customer_id

LEFT JOIN (
    SELECT customer_id, SUM(outstanding_amount) AS customer_total_overdue
    FROM loans
    WHERE CURRENT_DATE > due_date AND status != 'closed'
    GROUP BY customer_id
) ot ON ot.customer_id = l.customer_id

WHERE l.status != 'closed'
ORDER BY days_overdue DESC;
```

Replace `loans` / `repayments` with your actual table names, and this single query provides
everything the system needs to run all 5 AI pillars.
