# AI Collector — Architecture Document

## System Overview

AI Collector is a three-tier AI-native platform:

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                     │
│  ┌──────────────┐ ┌────────────┐ ┌───────────┐ ┌─────────┐ │
│  │  Executive   │ │ Collector  │ │  Invoice  │ │Scenario │ │
│  │  Dashboard   │ │  Worklist  │ │  Detail   │ │Simulator│ │
│  └──────────────┘ └────────────┘ └───────────┘ └─────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend (:8000)                     │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐  │
│  │  /predict  │ │/forecast │ │/recommend │ │/prioritize │  │
│  └────────────┘ └──────────┘ └───────────┘ └────────────┘  │
│                        │                │                   │
│                  ML Service         OpenAI GPT-4o           │
│                  HTTP Proxy           Agent                  │
└──────────┬────────────┼────────────────────────────────────┘
           │            │ HTTP
┌──────────▼──┐  ┌──────▼─────────────────────────────────┐
│ PostgreSQL  │  │          ML Service (:8001)              │
│ (invoices,  │  │  ┌───────────┐  ┌──────────┐  ┌──────┐ │
│  customers) │  │  │ XGBoost   │  │ LightGBM │  │ SHAP │ │
└─────────────┘  │  │ Payment   │  │ Risk     │  │ Expl │ │
                 │  └───────────┘  └──────────┘  └──────┘ │
                 └────────────────────────────────────────┘
```

## Service Responsibilities

### Frontend (`frontend/`)
- **Framework**: React 18 + Vite + TailwindCSS + Recharts
- **Routing**: React Router v6 (SPA, client-side)
- **API Client**: `src/lib/api.js` — typed fetch wrapper
- **State**: Local `useState` / `useEffect` hooks per page
- **Mock data**: `src/lib/mockData.js` — used when backend is unreachable

### Backend (`backend/`)
- **Framework**: Python 3.11 + FastAPI + Pydantic v2
- **Role**: Orchestration layer — routes requests, proxies ML service, runs OpenAI agent
- **Database**: SQLAlchemy 2 (async-compatible) → PostgreSQL
- **AI Layer**: OpenAI `AsyncOpenAI` client → GPT-4o structured JSON output
- **Fallback**: All services degrade gracefully to heuristic logic if dependencies are down

### ML Service (`ml-service/`)
- **Framework**: FastAPI (lightweight inference server)
- **Models**:
  - `payment_model_7d.pkl` — XGBoost binary classifier (paid in 7 days)
  - `payment_model_15d.pkl` — XGBoost binary classifier (paid in 15 days)
  - `payment_model_30d.pkl` — XGBoost binary classifier (paid in 30 days)
  - `risk_classifier_lgbm.pkl` — LightGBM multiclass (Low/Medium/High)
- **Explainability**: SHAP `TreeExplainer` for feature attribution
- **Training**: `training/train_payment.py` and `training/train_risk.py`

## Data Flow — Payment Prediction

```
1. Frontend POST /predict/payment  →  Backend
2. Backend validates request (Pydantic)
3. Backend POST /predict/payment   →  ML Service
4. ML Service loads XGBoost models from serialized_models/
5. ML Service builds feature vector (13 features + engineered)
6. XGBoost returns probabilities for 7/15/30 day horizons
7. Response flows back to Frontend
```

## Data Flow — AI Recommendation (GPT-4o Agent)

```
1. Frontend POST /recommend/action  →  Backend
2. Backend builds rich context prompt:
   - Invoice details
   - ML prediction outputs (p7, p15, p30)
   - Risk classification
   - Customer payment history
3. Backend calls OpenAI GPT-4o with JSON mode
4. Agent returns structured recommendation:
   {recommended_action, priority, timeline, reasoning}
5. Backend parses and validates JSON response
6. Frontend renders recommendation card
```

## Feature Engineering

All ML models share these 13 features:

| Feature | Description |
|---|---|
| `invoice_amount` | Invoice face value |
| `days_overdue` | Days past due date |
| `customer_credit_score` | Customer credit bureau score |
| `customer_avg_days_to_pay` | Historical average payment latency |
| `payment_terms` | Contractual payment terms (days) |
| `num_previous_invoices` | Total invoice count for customer |
| `num_late_payments` | Historical late payment count |
| `industry_encoded` | One-hot encoded industry (0–7) |
| `customer_total_overdue` | Total AR overdue for customer |
| `overdue_ratio` | days_overdue / payment_terms |
| `late_payment_rate` | num_late / num_previous |
| `log_amount` | log1p(invoice_amount) |
| `log_overdue_ar` | log1p(customer_total_overdue) |

## Priority Score Formula

```
Priority Score = invoice_amount × delay_probability

Where: delay_probability = 1 - pay_30_days
```

Invoices are sorted descending so collectors focus on highest-value, highest-risk items first.

## What-If Simulation Model

```
recovery += efficiency_pct × 0.8
recovery += discount_pct × 1.2
recovery += (-delay_days) × 0.4

cashflow_shift = efficiency_pct × 2560 - baseline_cashflow × (discount_pct / 100)
dso_shift = -delay_days × 0.5
```

## Development Team Split

| Developer | Service | Files |
|---|---|---|
| Data Scientist | `ml-service/` | training/, inference/, explainability/, datasets/ |
| Full-stack Dev 1 | `backend/` | services/, api/routes/, core/, schemas/ |
| Full-stack Dev 2 | `frontend/src/pages/` | All 4 page components + routing |
| Full-stack Dev 3 | `frontend/src/components/` | Charts, UI components, hooks |
