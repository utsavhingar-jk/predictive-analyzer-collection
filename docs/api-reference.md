# AI Collector — API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

---

## Health

### GET /health
Returns service status.

```json
{ "status": "ok", "service": "AI Collector API", "version": "1.0.0" }
```

---

## Predictions

### POST /predict/payment
Predict payment probability for a single invoice.

**Request body:**
```json
{
  "invoice_id": "INV-2024-001",
  "invoice_amount": 85000,
  "days_overdue": 45,
  "customer_credit_score": 580,
  "customer_avg_days_to_pay": 52.0,
  "payment_terms": 30,
  "num_previous_invoices": 5,
  "num_late_payments": 5,
  "industry": "manufacturing",
  "customer_total_overdue": 145000
}
```

**Response:**
```json
{
  "invoice_id": "INV-2024-001",
  "pay_7_days": 0.08,
  "pay_15_days": 0.18,
  "pay_30_days": 0.32,
  "model_version": "xgboost-v1"
}
```

---

### POST /predict/risk
Classify invoice risk level.

**Request body:** Same as `/predict/payment`

**Response:**
```json
{
  "invoice_id": "INV-2024-001",
  "risk_label": "High",
  "risk_score": 0.82,
  "confidence": 0.91,
  "model_version": "lgbm-v1"
}
```

---

### GET /predict/dso
Predict Days Sales Outstanding.

**Response:**
```json
{
  "predicted_dso": 52.3,
  "current_dso": 48.5,
  "dso_trend": "worsening",
  "benchmark_dso": 45.0
}
```

---

### POST /predict/explain
SHAP feature explanation for a prediction.

**Request body:**
```json
{
  "invoice_id": "INV-2024-001",
  "features": { "invoice_amount": 85000, "days_overdue": 45, ... }
}
```

**Response:**
```json
{
  "invoice_id": "INV-2024-001",
  "top_features": [
    { "feature_name": "days_overdue", "feature_value": 45, "shap_value": 0.32, "impact": "negative" }
  ],
  "base_value": 0.45,
  "prediction_value": 0.72
}
```

---

## Forecasting

### GET /forecast/cashflow
30-day cash inflow forecast with daily breakdown.

**Response:**
```json
{
  "next_7_days_inflow": 48200.0,
  "next_30_days_inflow": 187400.0,
  "confidence": 0.82,
  "daily_breakdown": [
    { "date": "2024-04-16", "predicted_inflow": 6100.0, "lower_bound": 4575.0, "upper_bound": 7625.0 }
  ]
}
```

---

## Invoices

### GET /invoices/summary
Portfolio-level summary metrics.

**Response:**
```json
{
  "total_invoices": 8,
  "total_outstanding": 484650.0,
  "overdue_count": 6,
  "risk_breakdown": { "High": 3, "Medium": 3, "Low": 2 }
}
```

---

### GET /invoices/
List invoices with optional filters.

**Query params:** `status`, `risk`, `limit`, `offset`

---

### GET /invoices/{invoice_id}
Get full invoice detail.

---

## Prioritization

### GET /prioritize/invoices
Priority-sorted collector worklist.

**Response:** Array of `PrioritizedInvoice`
```json
[
  {
    "invoice_id": "INV-2024-004",
    "customer_name": "TechNova Solutions",
    "amount": 125000,
    "days_overdue": 80,
    "risk_label": "High",
    "delay_probability": 0.82,
    "priority_score": 102500,
    "recommended_action": "Escalate to Collections Agency"
  }
]
```

---

## AI Recommendations

### POST /recommend/action
GPT-4o powered collection strategy recommendation.

**Request body:**
```json
{
  "invoice_id": "INV-2024-001",
  "invoice_amount": 85000,
  "days_overdue": 45,
  "risk_label": "High",
  "pay_7_days": 0.08,
  "pay_15_days": 0.18,
  "pay_30_days": 0.32,
  "customer_history": {
    "customer_name": "Apex Manufacturing Inc.",
    "avg_days_to_pay": 52.0,
    "num_late_payments": 5,
    "num_disputes": 0,
    "total_outstanding": 145000,
    "credit_score": 580,
    "industry": "manufacturing"
  }
}
```

**Response:**
```json
{
  "invoice_id": "INV-2024-001",
  "recommended_action": "Send Formal Demand Letter",
  "priority": "Critical",
  "timeline": "Within 24 Hours",
  "reasoning": "High-value invoice ($85K) is 45 days overdue with only 32% probability of payment in 30 days. Customer has 5 historical late payments.",
  "additional_notes": "Consider escalating to legal review if no response within 72 hours.",
  "model_used": "gpt-4o"
}
```

---

## What-If Simulation

### POST /whatif/simulate
Simulate the impact of strategy changes.

**Request body:**
```json
{
  "recovery_improvement_pct": 15,
  "discount_pct": 5,
  "delay_followup_days": -3
}
```

**Response:**
```json
{
  "predicted_recovery_pct": 82.6,
  "cashflow_shift": 18400.0,
  "dso_shift": -1.5,
  "baseline_recovery_pct": 68.0,
  "baseline_cashflow": 320000.0,
  "baseline_dso": 48.5,
  "scenario_summary": "Scenario: +15% efficiency, 5% discount, follow-up 3 days earlier."
}
```

---

## Error Responses

All endpoints return standard HTTP error codes:

```json
{ "detail": "Invoice INV-9999 not found" }
```

| Status | Meaning |
|---|---|
| 200 | Success |
| 404 | Resource not found |
| 422 | Validation error (check request schema) |
| 500 | Internal server error (check logs) |
