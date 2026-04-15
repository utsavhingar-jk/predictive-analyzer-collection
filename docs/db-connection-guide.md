# Database Connection Guide

## Step 1 — Set `DATABASE_URL` in `backend/.env`

```env
# ── Local Docker PostgreSQL (default) ──────────────────────────────────────────
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_collector

# ── Dev DB (your test server) ──────────────────────────────────────────────────
DATABASE_URL=postgresql://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>

# ── With SSL (most cloud DBs require this) ─────────────────────────────────────
DATABASE_URL=postgresql://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>?sslmode=require
```

Common examples:

| Environment | Example URL |
|---|---|
| Local Docker | `postgresql://postgres:postgres@localhost:5432/ai_collector` |
| Supabase | `postgresql://postgres:<pw>@db.<project>.supabase.co:5432/postgres` |
| AWS RDS | `postgresql://<user>:<pw>@<endpoint>.rds.amazonaws.com:5432/<db>` |
| Neon.tech | `postgresql://<user>:<pw>@<host>.neon.tech:5432/<db>?sslmode=require` |
| Railway | `postgresql://<user>:<pw>@<host>.railway.app:<port>/<db>` |

---

## Step 2 — Run the Schema

Connect to your DB and run the schema file:

```bash
# Using psql
psql $DATABASE_URL -f docs/database-schema.sql

# Or if running inside the Docker postgres container
docker exec -i ai-collector-postgres \
  psql -U postgres -d ai_collector \
  -f /dev/stdin < docs/database-schema.sql
```

This creates **8 tables**, **2 views**, and inserts **seed data** that mirrors the mock data already in the app.

---

## Step 3 — Wire the API to Real DB (replace mock_data.py)

The app currently reads from `backend/app/utils/mock_data.py`. To switch to your real DB, replace the service methods with SQLAlchemy queries. Below are the exact drop-in replacements for each route.

### `GET /invoices/summary` → replace `get_portfolio_summary()`

```python
from sqlalchemy import text
from app.core.database import SessionLocal

def get_portfolio_summary_from_db() -> dict:
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM v_portfolio_summary")).mappings().one()
        return {
            "total_invoices":    row["total_invoices"],
            "total_outstanding": float(row["total_outstanding"] or 0),
            "overdue_count":     row["overdue_count"],
            "overdue_amount":    float(row["overdue_amount"] or 0),
            "amount_at_risk":    float(row["amount_at_risk"] or 0),
            "high_risk_count":   row["high_risk_count"],
            "risk_breakdown": {
                "High":   row["high_risk_count"],
                "Medium": row["medium_risk_count"],
                "Low":    row["low_risk_count"],
            },
        }
```

### `GET /prioritize/invoices` → replace `get_prioritized_worklist()`

```python
def get_worklist_from_db() -> list[dict]:
    with SessionLocal() as db:
        rows = db.execute(text("SELECT * FROM v_collector_worklist")).mappings().all()
        return [dict(r) for r in rows]
```

### `GET /invoices/{invoice_id}` → replace `get_invoice_by_id()`

```python
INVOICE_DETAIL_SQL = """
SELECT
    i.invoice_number AS invoice_id,
    i.invoice_number,
    c.id             AS customer_id,
    c.name           AS customer_name,
    c.industry,
    i.amount,
    i.currency,
    i.issue_date,
    i.due_date,
    i.status,
    i.days_overdue,
    c.credit_score,
    c.avg_days_to_pay,
    c.num_late_payments,
    ip.pay_7_days,
    ip.pay_15_days,
    ip.pay_30_days,
    ip.delay_probability,
    ip.risk_tier     AS risk_label,
    ip.top_drivers,
    ip.shap_values,
    cs.priority_score,
    cs.recommended_action,
    cs.urgency,
    cs.channel,
    cs.reason,
    cb.behavior_type,
    cb.on_time_ratio,           -- Add this column to customer_behavior if needed
    cb.avg_delay_days,
    cb.behavior_risk_score,
    cb.trend,
    cb.payment_style,
    cb.followup_dependency,
    cb.nach_recommended,
    cb.behavior_summary
FROM invoices i
JOIN customers c ON c.id = i.customer_id
LEFT JOIN customer_behavior cb ON cb.customer_id = c.id
LEFT JOIN LATERAL (
    SELECT * FROM invoice_predictions
    WHERE invoice_id = i.id ORDER BY predicted_at DESC LIMIT 1
) ip ON TRUE
LEFT JOIN LATERAL (
    SELECT * FROM collection_strategies
    WHERE invoice_id = i.id ORDER BY computed_at DESC LIMIT 1
) cs ON TRUE
WHERE i.invoice_number = :invoice_id
"""

def get_invoice_by_id_from_db(invoice_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(text(INVOICE_DETAIL_SQL), {"invoice_id": invoice_id}).mappings().one_or_none()
        if not row:
            return None
        result = dict(row)
        # Deserialize JSONB fields
        result["top_drivers"]  = result.get("top_drivers")  or []
        result["shap_values"]  = result.get("shap_values")  or []
        # Serialize dates
        for f in ("issue_date", "due_date"):
            if hasattr(result.get(f), "isoformat"):
                result[f] = result[f].isoformat()
        return result
```

---

## Step 4 — Map Your Real Data

Your production database may use different column names. Use this field mapping table to adapt:

| App Field | DB Column | Table | Notes |
|---|---|---|---|
| `invoice_id` | `invoice_number` | `invoices` | e.g. `INV-2024-001` |
| `customer_name` | `name` | `customers` | |
| `amount` | `amount` | `invoices` | NUMERIC(14,2) |
| `days_overdue` | `days_overdue` | `invoices` | Recompute nightly: `GREATEST(0, NOW()::DATE - due_date)` |
| `credit_score` | `credit_score` | `customers` | 300–850 |
| `avg_days_to_pay` | `avg_days_to_pay` | `customers` | Rolling average |
| `num_late_payments` | `num_late_payments` | `customers` | Count of historical late invoices |
| `pay_30_days` | `pay_30_days` | `invoice_predictions` | Output of ML model |
| `delay_probability` | `delay_probability` | `invoice_predictions` | `1 - pay_30_days` |
| `risk_tier` | `risk_tier` | `invoice_predictions` | High/Medium/Low |
| `behavior_type` | `behavior_type` | `customer_behavior` | |
| `priority_score` | `priority_score` | `collection_strategies` | 0–100 |

---

## Step 5 — Keep `days_overdue` Fresh (Nightly Job)

Add a scheduled SQL job (pg_cron, cron, or your scheduler) to recompute overdue status daily:

```sql
-- Run nightly at midnight
UPDATE invoices
SET
    days_overdue = GREATEST(0, NOW()::DATE - due_date),
    status = CASE
        WHEN paid_date IS NOT NULL THEN 'paid'
        WHEN NOW()::DATE > due_date THEN 'overdue'
        ELSE 'open'
    END,
    updated_at = NOW()
WHERE status != 'paid';
```
