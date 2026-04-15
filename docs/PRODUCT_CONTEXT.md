# AI Collector — Full Product Context Document

> **For:** Product Managers, Stakeholders, and Team Leads  
> **Purpose:** Complete reference for the AI Collector platform — what it does, how it works, why each feature exists, and how to demo it.

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Problem We Are Solving](#2-problem-we-are-solving)
3. [What Makes This AI-Native](#3-what-makes-this-ai-native)
4. [User Personas](#4-user-personas)
5. [The 5 Intelligence Pillars](#5-the-5-intelligence-pillars)
6. [User Journey — Screen by Screen](#6-user-journey--screen-by-screen)
7. [Agentic AI — How It Works](#7-agentic-ai--how-it-works)
8. [Tech Stack](#8-tech-stack)
9. [System Architecture](#9-system-architecture)
10. [Complete API Reference](#10-complete-api-reference)
11. [Data Model](#11-data-model)
12. [ML Models](#12-ml-models)
13. [Current State vs Production Path](#13-current-state-vs-production-path)
14. [Team Workstreams](#14-team-workstreams)
15. [Demo Script](#15-demo-script)

---

## 1. Product Vision

**AI Collector** is an intelligent receivables optimization platform for B2B lenders and corporate finance teams. It replaces reactive, manual collections workflows with an AI-driven system that:

- **Predicts** which invoices will be delayed *before* they are due
- **Profiles** borrower payment personalities from historical behavior
- **Prioritizes** collector workloads by risk-weighted urgency
- **Recommends** the exact collection action, channel, and SLA for every invoice
- **Forecasts** how much cash will actually arrive in the next 7 and 30 days
- **Aggregates** borrower-level risk across all their open invoices
- **Explains** every decision in plain English via a GPT-4o agent

This is **not a dashboard** that shows data after the fact. It is a **decision-support engine** that tells collectors *what to do* and *why*, before problems become write-offs.

---

## 2. Problem We Are Solving

### The Traditional Collections Problem

| Pain Point | Reality |
|---|---|
| Collectors work from age buckets (30/60/90 DPD) | No intelligence about which invoice will actually default |
| High-value customers always get attention | A $10K invoice with 95% default probability is more urgent than a $100K invoice at 5% risk |
| No borrower-level view | Collector treats each invoice as isolated, missing the full relationship picture |
| Cash flow forecasting is manual | Finance team manually estimates inflows with no probabilistic model |
| Escalation decisions are gut-feel | No data-driven rule for when to move from email to legal |
| Follow-up timing is fixed (every 7 days) | Ignores that some borrowers respond only after pressure, others pay on reminder |

### What AI Collector Changes

Instead of "INV-001 is 45 days overdue → send reminder", the system says:

> *"INV-2024-001 (Apex Manufacturing, $85,000) has an 82% delay probability. The borrower is a Chronic Delayed Payer with a worsening trend. Priority score is 95/100. Action: Call within 2 hours + activate NACH mandate. $145,000 of their total exposure is at risk."*

---

## 3. What Makes This AI-Native

Most AR platforms are CRUD dashboards — they show you data. AI Collector is different in 3 ways:

### 3.1 Predictive, Not Reactive
Every invoice has a `delay_probability` computed from invoice features + borrower history + behavior signals. The system acts on future risk, not past buckets.

### 3.2 Behavior-Aware
The system builds a **payment personality profile** for every borrower — not just credit score, but behavioral signals: on-time ratio, deterioration trend, whether they pay only after followup, partial payment frequency. This feeds directly into delay prediction.

### 3.3 Truly Agentic
The AI agent (GPT-4o with function calling) doesn't just narrate results — it **drives its own investigation**. When you ask "Should I escalate TechNova?", the agent autonomously:
1. Decides to fetch invoice details first
2. Then analyzes payment behavior
3. Then predicts delay using those behavior signals
4. Then derives the collection strategy
5. Then writes a business-readable recommendation

The agent's tool call sequence and reasoning are visible in the UI as a step-by-step trace.

---

## 4. User Personas

### Persona 1: The Collections Manager (Executive)
**Goal:** Portfolio-level visibility. Which customers are high risk? What is our cash flow exposure? Do we need to flag anything to leadership?

**Uses:** Executive Dashboard, Borrower Portfolio page, Portfolio Summary KPIs

### Persona 2: The Collector (Frontline)
**Goal:** Know exactly which invoice to call on first and what to say. Don't waste time on low-priority cases.

**Uses:** Collector Worklist (ranked by priority), Invoice Detail page, Collection strategy card

### Persona 3: The Credit Analyst
**Goal:** Understand a specific borrower's full risk picture before making a credit decision.

**Uses:** Borrower Portfolio, Invoice Detail with full AI analysis, Delay drivers, SHAP explanation

### Persona 4: The CFO / Finance Team
**Goal:** Accurate cash flow forecast. How much cash will actually arrive this month? What is at risk?

**Uses:** Executive Dashboard cashflow chart, Expected 7-day and 30-day collections, Shortfall signal

---

## 5. The 5 Intelligence Pillars

The system is built around 5 connected layers. Each feeds the next.

```
[Pillar 1]  Payment Behavior Engine
      ↓  (behavior profile feeds delay model)
[Pillar 2]  Delay Prediction Engine
      ↓  (delay probability feeds strategy)
[Pillar 3]  Collection Strategy Optimization
      ↓  (all predictions feed forecast)
[Pillar 4]  Cash Flow Forecast Engine
      ↓  (all pillars feed the agent)
[Pillar 5]  OpenAI GPT-4o Agentic Layer
```

---

### Pillar 1 — Payment Behavior Engine

**API:** `POST /analyze/payment-behavior`  
**Service:** `backend/app/services/behavior_service.py`

**What it does:** Takes a borrower's historical payment signals and classifies their payment *personality*.

**Input signals (9 features):**

| Signal | Meaning |
|---|---|
| `historical_on_time_ratio` | % of invoices paid on time (0–1) |
| `avg_delay_days` | Average days late on historical payments |
| `repayment_consistency` | How consistent their timing is (0–1) |
| `partial_payment_frequency` | How often they pay partial amounts |
| `prior_delayed_invoice_count` | Raw count of historical delays |
| `payment_after_followup_count` | Times they only paid after a reminder |
| `deterioration_trend` | -1 = improving, 0 = stable, +1 = worsening |
| `invoice_acknowledgement_behavior` | "normal", "slow", "disputes" |
| `transaction_success_failure_pattern` | Failed payment attempt ratio |

**Output:**

```json
{
  "behavior_type": "Chronic Delayed Payer",
  "on_time_ratio": 20,
  "avg_delay_days": 72,
  "trend": "Worsening",
  "payment_style": "Reminder Driven",
  "behavior_risk_score": 84,
  "followup_dependency": true,
  "nach_recommended": true,
  "behavior_summary": "This borrower consistently pays late with a worsening trend..."
}
```

**Behavior Types:**
- `Chronic Delayed Payer` — on-time ratio < 35% AND avg delay > 15 days
- `Deteriorating Payer` — deterioration trend > 0.4
- `Partial Payer` — pays frequently in partial amounts
- `Reliable Payer` — on-time ratio > 80%
- `Occasional Delayed Payer` — everything else

**Risk score formula:**
```
behavior_risk_score =
  (1 - on_time_ratio) × 40
  + min(avg_delay / 30, 1) × 25
  + (1 - consistency) × 15
  + deterioration_trend × 10
  + partial_frequency × 10
```

---

### Pillar 2 — Delay Prediction Engine

**API:** `POST /predict/delay`  
**Service:** `backend/app/services/delay_service.py`

**What it does:** Predicts whether a specific invoice will be delayed, using both invoice facts and the behavior profile from Pillar 1.

**Why this matters:** Invoice-level facts alone (amount, DPD) miss the person behind the invoice. A $10K invoice from a Chronic Delayed Payer is more urgent than a $100K invoice from a Reliable Payer.

**Key inputs:**
- Invoice: amount, days overdue, payment terms, credit score
- Behavior: behavior_type, on_time_ratio, avg_delay_days, deterioration_trend

**How delay probability is calculated:**
```
base_prob = days_overdue / (days_overdue + payment_terms)

Additive risk factors:
  credit_score < 600          → +15%
  num_late_payments > 3       → +10%
  invoice > 2× avg amount     → +8%
  behavior = "Chronic"        → +15%
  behavior = "Deteriorating"  → +10%
  deterioration_trend > 0.3   → +8%
  on_time_ratio < 40%         → +7%

delay_probability = min(0.99, base + all adjustments)
```

**Risk score and tier:**
```
risk_score = delay_probability × 100 + behavior_risk_score × 0.3 + credit_factor × 10

risk_tier:
  score ≥ 65 → High
  score ≥ 35 → Medium
  else       → Low
```

**Output:**
```json
{
  "delay_probability": 0.91,
  "risk_score": 89,
  "risk_tier": "High",
  "top_drivers": [
    "8 prior late payments",
    "Invoice 3.1× average amount",
    "Behavior: Chronic Delayed Payer",
    "Credit score below 600"
  ],
  "model_version": "delay-v2"
}
```

---

### Pillar 3 — Collection Strategy Optimization

**API:** `POST /optimize/collection-strategy`  
**Service:** `backend/app/services/strategy_service.py`

**What it does:** Takes Pillar 2's delay prediction and determines the optimal collection action — what to do, through which channel, by when.

**Priority score formula (0–100):**
```
base          = delay_probability × 50         (max 50 pts)
amount        = min(amount / 200,000, 1) × 20  (max 20 pts)
overdue       = min(days_overdue / 90, 1) × 15 (max 15 pts)
behavior      = +10 if Chronic or Deteriorating
nach          = +5 if NACH applicable

priority_score = base + amount + overdue + behavior + nach
```

**Urgency tiers:**
```
score ≥ 80 → Critical
score ≥ 60 → High
score ≥ 40 → Medium
else       → Low
```

**Action Matrix:**

| Urgency | NACH | Recommended Action | Channel | SLA |
|---|---|---|---|---|
| Critical | Yes | Call + NACH Mandate | Call | 2 hours |
| Critical | No | Escalate to Management | Call | 4 hours |
| High | Yes | NACH + Reminder Call | Call | 24 hours |
| High | No | Escalate to Collections | Call | 24 hours |
| Medium | — | Send Payment Reminder | Email | 48 hours |
| Low | — | Auto Email Reminder | Email | 72 hours |

**Output:**
```json
{
  "priority_score": 95,
  "priority_rank": 1,
  "recommended_action": "Call + NACH Mandate",
  "urgency": "Critical",
  "channel": "Call",
  "reason": "High delay risk + high amount + NACH applicable",
  "automation_flag": false,
  "next_action_in_hours": 2
}
```

---

### Pillar 4 — Cash Flow Forecast Engine

**API:** `GET /forecast/cashflow`  
**Service:** `backend/app/services/cashflow_service.py`

**What it does:** Uses predicted payment probabilities across all invoices to forecast realistic cash inflows — not optimistic due-date assumptions.

**How it works:**
```
For every open invoice:
  expected_inflow += invoice.amount × pay_probability

amount_at_risk = sum of invoice amounts where delay_probability > 60%

overdue_carry_forward = total amount already past due (still expected to collect)

shortfall_signal = true if expected_inflow < 70% of total outstanding

borrower_concentration_risk:
  any single borrower > 40% of total AR → "High"
  any single borrower > 20% of total AR → "Medium"
  else                                   → "Low"
```

**Output:**
```json
{
  "next_7_days_inflow": 85000,
  "next_30_days_inflow": 320000,
  "expected_7_day_collections": 72000,
  "expected_30_day_collections": 285000,
  "amount_at_risk": 210000,
  "shortfall_signal": true,
  "borrower_concentration_risk": "Medium",
  "overdue_carry_forward": 145000,
  "confidence": 0.78
}
```

---

### Pillar 5 — OpenAI GPT-4o Agentic Layer

**API:** `POST /agent/analyze-case` and `POST /agent/ask`  
**Service:** `backend/app/services/agent_service.py`

**What it does:** GPT-4o autonomously calls tools, reasons over results, and produces a business-ready recommendation. It is not given a fixed script — it decides what to investigate based on the question.

**6 tools available to the agent:**

| Tool | What GPT-4o uses it for |
|---|---|
| `get_invoice_details` | Fetch raw invoice facts when only an ID is provided |
| `analyze_payment_behavior` | Understand the borrower's payment personality |
| `predict_invoice_delay` | Compute delay probability enriched with behavior |
| `optimize_collection_strategy` | Determine action, urgency, channel, SLA |
| `get_borrower_risk` | Aggregate risk across all of a customer's invoices |
| `get_portfolio_summary` | Check overall portfolio health |

**How the ReAct loop works:**
```
1. User sends: "Should I escalate INV-2024-004?"

2. GPT-4o thinks → calls get_invoice_details("INV-2024-004")
   Sees: 80 days overdue, $125K, TechNova Solutions

3. GPT-4o thinks → calls analyze_payment_behavior(customer_id="4", ...)
   Sees: "Chronic Delayed Payer", 20% on-time, worsening trend

4. GPT-4o thinks → calls predict_invoice_delay(invoice_id="INV-2024-004", ...)
   Sees: 91% delay probability, High tier

5. GPT-4o thinks → calls optimize_collection_strategy(...)
   Sees: Priority 95/100, Critical urgency, NACH + Call within 2 hours

6. GPT-4o has enough context → writes final recommendation:
   "Yes, escalate immediately. TechNova is a Chronic Delayed Payer
   with a worsening trend. 80 days overdue, 91% delay probability.
   Activate NACH mandate and escalate to legal within 2 hours."

7. Every tool call, the input, and key outputs are recorded in reasoning_trace
   and displayed to the user step by step.
```

**Free-form questions the agent can answer:**
- "Should I escalate this invoice?"
- "What is the payment behavior of TechNova Solutions?"
- "Which invoices are at highest risk today?"
- "What is our cash flow risk this month?"
- "Analyze customer 4 and tell me what to do"

---

## 6. User Journey — Screen by Screen

### Screen 1: Executive Dashboard (`/`)

**Who uses it:** Collections Manager, CFO  
**Loads:** `GET /forecast/cashflow` + `GET /prioritize`

**What it shows:**
- **Total Outstanding** — sum of all open AR
- **Amount at Risk** — AR where delay probability > 60%
- **High-Risk Invoices** — count of High tier invoices
- **Expected 30-Day Collections** — probability-weighted forecast
- **Shortfall Signal Banner** — red warning if expected inflow < 70% of outstanding
- **Cashflow Forecast Chart** — 7-day and 30-day bar chart (expected vs at-risk)
- **Risk Breakdown Pie Chart** — portfolio split by High / Medium / Low
- **Top Priority Cases Table** — top 5 invoices by priority score

---

### Screen 2: Collector Worklist (`/worklist`)

**Who uses it:** Frontline collectors  
**Loads:** `GET /optimize/portfolio-strategy`

**What it shows** (per invoice row):
- **Rank** — priority order (1 = most urgent)
- **Invoice ID** — clickable to detail
- **Customer** — name + industry
- **Amount** — invoice value
- **Risk Tier** — High / Medium / Low badge
- **Behavior Badge** — "Chronic", "Reliable", etc.
- **NACH Flag** — indicator if NACH mandate is recommended
- **Priority Score** — 0–100 bar with color
- **Urgency Badge** — Critical / High / Medium / Low
- **Recommended Action** — e.g. "Call + NACH Mandate"

Collectors work top-to-bottom. Rank 1 gets called first.

---

### Screen 3: Borrower Portfolio (`/borrowers`)

**Who uses it:** Credit Analysts, Collections Manager  
**Loads:** `GET /predict/borrowers/portfolio`

**What it shows:**
- **KPI Row:** Total Exposure, High-Risk Borrowers, Amount at Risk, Escalations Required
- **Ranked Table** (all customers, sorted by borrower risk score):
  - Exposure + portfolio concentration %
  - Risk tier and score bar
  - Weighted delay probability
  - Expected recovery rate bar
  - At-risk amount
  - Relationship-level action
  - Escalation flag

**Click any row** → side drawer opens with full borrower detail:
  - Risk score breakdown
  - Recovery forecast
  - Delay probability
  - Relationship action
  - "View Full Borrower Analysis" button

**Why this matters:** A customer may have 3 low-risk invoices and 1 critical invoice. Borrower-level view shows the full relationship — total exposure, overall delay risk, and whether the entire credit facility should be reviewed.

---

### Screen 4: Invoice Detail Page (`/invoices/:id`)

**Who uses it:** Collectors researching a specific invoice  
**Loads:** `GET /invoices/:id` + `GET /predict/borrower/:customerId`

**Row 1 — Three core cards:**
- **Invoice Details** — all invoice fields (ID, amount, dates, status, DPD, risk badge)
- **Payment Probability** — 7-day / 15-day / 30-day probability bars from ML model
- **AI Recommendation** — urgency, action, SLA, reasoning (from strategy engine)

**Row 2 — Four AI intelligence cards:**
- **Payment Behavior Card** — behavior type, on-time ratio, trend, risk score, NACH flag
- **Delay Prediction Card** — delay probability gauge, risk tier, top 3 drivers
- **Collection Strategy Card** — priority score, urgency, channel, SLA, reason
- **Borrower Risk Card** — aggregate risk across all customer invoices

**Agent Section:**
- **"Run Full AI Analysis" button** — triggers the full ReAct agent loop
- **Agent Reasoning Trace** — timeline showing every tool GPT called, with thoughts and key outputs
- **Expandable raw I/O** — see exact inputs/outputs for each tool call

**Agent Ask Box:**
- Type any question about this invoice or customer
- Agent autonomously investigates and responds
- Shows full reasoning trace

**SHAP Explanation Chart:**
- Bar chart showing feature importance (why the model scored this invoice as it did)

---

### Screen 5: Scenario Simulator (`/simulator`)

**Who uses it:** Collections Manager, CFO for what-if planning  
**Loads:** `POST /whatif/scenario`

**Sliders:**
- Recovery Improvement % — if collectors increase efficiency
- Early Payment Discount % — if you offer incentives
- Delay Follow-up Days — if you delay outreach

**Shows:** Impact on predicted recovery %, cashflow shift, DSO shift

---

## 7. Agentic AI — How It Works

### What "Agentic" Means in This Context

| Property | Implementation |
|---|---|
| **Autonomy** | GPT-4o decides which tools to call and in what order |
| **Tool Use** | 6 backend tools exposed via OpenAI function calling |
| **Reasoning Loop** | ReAct: Reason → Act → Observe → Reason again (up to 8 iterations) |
| **Traceability** | Every tool call, input, output, and GPT thought is logged in `reasoning_trace` |

### What Happens When You Click "Run Full AI Analysis"

```
Frontend sends:  POST /agent/analyze-case
                 { invoice_id, customer_id, invoice_amount, days_overdue, ... }

Backend:
  1. AgentService._react_loop() starts
  2. GPT-4o receives system prompt + invoice context + list of 6 tools
  3. GPT-4o calls tools autonomously (typically 4–5 calls):
       get_invoice_details → analyze_payment_behavior
       → predict_invoice_delay → optimize_collection_strategy
  4. After each tool call result is returned, GPT-4o reasons again
  5. When GPT-4o has enough context, finish_reason = "stop"
  6. GPT-4o writes the final business_summary
  7. All tool calls recorded in reasoning_trace

Frontend:
  AgentReasoningTrace component renders the timeline
  Each step shows: tool name, GPT's thought, key outputs
  Expandable to see raw JSON in/out
```

### Free-Form Agent Questions (`POST /agent/ask`)

The user can type any question in natural language. The agent starts with no context — it must use tools to discover what it needs.

Example: *"What is the payment behavior of TechNova and should their credit facility be reviewed?"*

The agent might call:
1. `get_invoice_details` (finds TechNova's invoices)
2. `analyze_payment_behavior` (profiles the customer)
3. `get_borrower_risk` (aggregates all their invoices)
4. Writes recommendation

---

## 8. Tech Stack

### Frontend
| Technology | Purpose |
|---|---|
| React 18 + Vite | SPA framework |
| React Router v6 | Client-side routing |
| TailwindCSS + ShadCN UI | Styling and component library |
| Recharts | Charts (cashflow, risk pie, SHAP bars) |
| Lucide React | Icons |

### Backend
| Technology | Purpose |
|---|---|
| Python 3.11 + FastAPI | API framework |
| Pydantic v2 | Request/response validation and serialization |
| SQLAlchemy 2 | ORM (connected to PostgreSQL) |
| httpx | Async HTTP client for ML service calls |
| OpenAI Python SDK | GPT-4o function calling |
| pydantic-settings | Config from `.env` file |

### ML Service
| Technology | Purpose |
|---|---|
| XGBoost | Binary classifier — payment probability |
| LightGBM | Multi-class classifier — risk tier |
| scikit-learn | Feature preprocessing |
| SHAP | Feature importance / explainability |
| pandas + numpy | Data processing |
| FastAPI | ML inference HTTP service |

### Infrastructure
| Technology | Purpose |
|---|---|
| Docker + Docker Compose | Container orchestration |
| PostgreSQL 16 | Primary database |
| Nginx | Frontend serving in production |

---

## 9. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                       BROWSER                            │
│                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Executive  │  │  Collector  │  │  Invoice Detail  │  │
│  │ Dashboard  │  │  Worklist   │  │  + Agent UI      │  │
│  └────────────┘  └─────────────┘  └──────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │Borrower Portfolio│  │   Scenario Simulator         │  │
│  └──────────────────┘  └──────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP/JSON (port 8000)
┌───────────────────────▼──────────────────────────────────┐
│                   FASTAPI BACKEND                        │
│                                                          │
│  Routes: /forecast /predict /optimize /agent /borrower  │
│          /invoices /recommend /prioritize /analyze       │
│                                                          │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │   Behavior   │ │    Delay    │ │    Strategy      │  │
│  │   Service    │ │   Service   │ │    Service       │  │
│  └──────────────┘ └─────────────┘ └──────────────────┘  │
│  ┌──────────────┐ ┌─────────────┐ ┌──────────────────┐  │
│  │  Cashflow    │ │   Borrower  │ │   Agent Service  │  │
│  │  Service     │ │   Service   │ │  (ReAct + Tools) │  │
│  └──────────────┘ └─────────────┘ └────────┬─────────┘  │
└─────────────────────────────────────────────┼────────────┘
              │                               │
    HTTP/JSON │                     OpenAI API│
    (port 8001│)                              │ GPT-4o
┌─────────────▼──────┐              ┌─────────▼──────────┐
│    ML SERVICE      │              │   OPENAI CLOUD     │
│                    │              │                    │
│  XGBoost (payment) │              │  Function Calling  │
│  LightGBM (risk)   │              │  ReAct Loop        │
│  SHAP (explain)    │              │  GPT-4o            │
└────────────────────┘              └────────────────────┘
              │
┌─────────────▼──────────────────────────────────────────┐
│               POSTGRESQL DATABASE                       │
│  customers / invoices / predictions / strategies       │
│  cashflow_snapshots / agent_case_results               │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Complete API Reference

### Prediction Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/predict/payment` | Payment probability for 7/15/30 days |
| `POST` | `/predict/risk` | Risk classification: High/Medium/Low |
| `POST` | `/predict/delay` | Delay probability + risk tier + drivers |
| `GET` | `/predict/dso` | Predicted Days Sales Outstanding |
| `POST` | `/predict/borrower` | Full borrower-level risk prediction |
| `GET` | `/predict/borrower/{customer_id}` | Borrower prediction by customer ID |
| `GET` | `/predict/borrowers/portfolio` | All borrowers ranked by risk score |

### Behavior Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/analyze/payment-behavior` | Analyze borrower payment personality |
| `GET` | `/analyze/payment-behavior/{customer_id}` | Behavior profile by customer ID |

### Strategy Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/optimize/collection-strategy` | Optimal action for one invoice |
| `GET` | `/optimize/portfolio-strategy` | Strategy for all invoices (ranked worklist) |

### Forecast Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/forecast/cashflow` | 7-day and 30-day cash flow forecast |
| `GET` | `/forecast/dso` | DSO trend forecast |

### Agent Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/agent/analyze-case` | Full agentic analysis of one invoice case |
| `POST` | `/agent/ask` | Free-form natural language question |

### Other Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/invoices` | All invoices (paginated) |
| `GET` | `/invoices/{invoice_id}` | Single invoice with all predictions |
| `POST` | `/recommend/action` | OpenAI prescriptive recommendation |
| `GET` | `/prioritize` | Prioritized invoice list (legacy) |
| `POST` | `/whatif/scenario` | What-if scenario simulation |
| `GET` | `/health` | Service health check |

---

## 11. Data Model

### 8 Core Database Tables

```sql
customers              — customer master data, credit score, contact info
customer_behavior      — payment behavior profile per customer
invoices               — invoice ledger with status and payment terms
invoice_predictions    — ML predictions per invoice (payment probs, risk, delay)
collection_strategies  — recommended actions per invoice
cashflow_snapshots     — daily forecast snapshots
agent_case_results     — GPT-4o reasoning traces per analyzed case
payment_transactions   — raw payment event log
```

### 2 Optimized Views

```sql
v_collector_worklist   — pre-joined view for the Collector Worklist page
v_portfolio_summary    — aggregate KPIs for the Executive Dashboard
```

Full schema available at: `docs/database-schema.sql`  
DB connection guide at: `docs/db-connection-guide.md`

### Demo Dataset (Mock Data)

8 borrowers across 8+ invoices covering all risk scenarios:

| Customer | Industry | Risk | Scenario |
|---|---|---|---|
| TechNova Solutions | Technology | High | 80 DPD, 91% delay prob, NACH candidate |
| Apex Manufacturing | Manufacturing | High | 45 DPD, chronic delayed payer |
| Pacific Steel Works | Manufacturing | High | High DPD, nach recommended |
| BlueSky Logistics | Logistics | Medium | 20 DPD, occasional delays |
| NorthStar Healthcare | Healthcare | Medium | 35 DPD, partial payer |
| Solaris Energy | Energy | Low | Current, reliable payer |
| GreenField Retail | Retail | Low | 5 DPD, first-time late |
| Clearwater Financial | Finance | Low | Current, excellent history |

---

## 12. ML Models

### Model 1: Payment Predictor (XGBoost)

**File:** `ml-service/training/train_payment.py`  
**Output:** `pay_7_days`, `pay_15_days`, `pay_30_days` (0–1 probabilities)

**Features used:**
- days_overdue, invoice_amount, payment_terms
- credit_score, avg_days_to_pay, num_late_payments
- customer_total_overdue, customer_avg_invoice_amount

**Training:** XGBoost binary classifier trained per time horizon on `datasets/invoices.csv`

### Model 2: Risk Classifier (LightGBM)

**File:** `ml-service/training/train_risk.py`  
**Output:** `risk_label` (High / Medium / Low), `risk_probabilities`

**Features used:** Same feature set as payment predictor

**Training:** LightGBM multi-class classifier

### SHAP Explainability

**File:** `ml-service/explainability/shap_explainer.py`  
**Output:** Feature importance values per prediction  
**Visualized:** Bar chart on Invoice Detail page  
**Purpose:** Explains *why* an invoice got its risk score (e.g. "credit_score contributed -0.32")

### Current Status

| Model | Status | Used In |
|---|---|---|
| XGBoost payment predictor | Trained in Docker container | `pay_7/15/30_days` on invoice cards |
| LightGBM risk classifier | Trained in Docker container | `risk_label` on all views |
| Behavior classifier | Rule-based (ML placeholder ready) | Pillar 1 classification |
| Delay predictor | Rule-based (ML placeholder ready) | Pillar 2 delay probability |

**To retrain models inside Docker:**
```bash
docker exec ai-collector-ml-service python training/train_payment.py
docker exec ai-collector-ml-service python training/train_risk.py
docker restart ai-collector-ml-service
```

---

## 13. Current State vs Production Path

### Current State (Hackathon / Demo)
- Mock data in `backend/app/utils/mock_data.py` (8 borrowers, 8+ invoices)
- Rule-based engines for Behavior and Delay Prediction (fallbacks to ML)
- XGBoost + LightGBM trained on synthetic CSV dataset
- OpenAI GPT-4o fully live (requires valid API key in `backend/.env`)
- All Docker containers running and interconnected

### Production Path

| Area | What Needs Changing |
|---|---|
| **Data** | Replace `MOCK_INVOICES` with SQLAlchemy queries to live DB |
| **Behavior ML** | Train XGBoost/LGBM on real payment history; replace rule engine in `behavior_service.py` |
| **Delay ML** | Train dedicated delay model; replace rule engine in `delay_service.py` |
| **Auth** | Add JWT authentication to all API endpoints |
| **Database** | Run `docs/database-schema.sql` on production PostgreSQL |
| **Monitoring** | Add logging/alerting for prediction drift and OpenAI failures |
| **Scheduler** | Nightly job to update `days_overdue` and refresh ML predictions |

Full DB migration guide: `docs/db-connection-guide.md`

---

## 14. Team Workstreams

### Data Scientist
- Own `ml-service/` entirely
- Train production-grade XGBoost model on real payment data
- Train LightGBM risk classifier
- Build behavior classification ML model (replace current rule engine)
- Build delay prediction ML model (replace current rule engine)
- Calibrate SHAP explanations for production feature set

### Developer 1 — Backend Core
- Own `backend/app/services/` and `backend/app/schemas/`
- Connect DB queries (replace mock data functions)
- Add authentication layer
- Build production cashflow snapshot scheduler

### Developer 2 — Backend Agent + ML Integration
- Own `backend/app/services/agent_service.py`
- Integrate production ML models when Data Scientist delivers them
- Extend agent tools (add `search_similar_borrowers`, `get_payment_history`)
- Add streaming support to `/agent/ask` for real-time token output

### Developer 3 — Frontend
- Own `frontend/src/`
- Polish all 5 pages for production
- Add dark/light mode toggle
- Add real-time notifications (shortfall signal push alert)
- Build full Borrower Detail page (individual customer deep-dive)
- Mobile-responsive layout

---

## 15. Demo Script

**Use this script when presenting to stakeholders:**

### Step 1 — Executive View
> Open Executive Dashboard. Point to the shortfall signal banner.
> "Our system is flagging a cash flow shortfall — only 68% of our outstanding AR is expected to come in within 30 days. $262,000 is at risk."

### Step 2 — Prioritized Worklist
> Open Collector Worklist.
> "Instead of collectors working alphabetically or by DPD bucket, they get a priority-ranked list. INV-2024-004 is rank 1 because it has a 91% delay probability, $125,000 exposure, and the borrower is a Chronic Delayed Payer."

### Step 3 — Invoice Deep Dive with AI
> Click INV-2024-004 (TechNova Solutions).
> "Here we see all 5 intelligence layers at once. The behavior card says Chronic Delayed Payer, worsening trend. The delay card says 91% probability, risk score 89/100. The strategy card says call + activate NACH within 2 hours."

### Step 4 — Run the Agent
> Click "Run Full AI Analysis".
> "Now watch the agent. It didn't just get told what to do — it decided to first fetch the invoice details, then profile the borrower's payment behavior, then predict delay using those signals, then derive the strategy. Each step is visible. This is the ReAct pattern — the agent reasons between every tool call."

### Step 5 — Ask a Free-Form Question
> Type: "Should we suspend TechNova's credit facility?"
> "The agent will now investigate autonomously and give us a recommendation."

### Step 6 — Borrower Portfolio
> Open Borrower Portfolio.
> "At the relationship level, TechNova represents 28.9% of our total portfolio. That's a concentration risk. $125,000 outstanding, only 18% expected recovery rate. Escalation is recommended. This view helps us make credit facility decisions, not just invoice-level actions."

### Step 7 — Cashflow Forecast
> Back to Executive Dashboard, point to the chart.
> "This isn't optimistic 'assume everyone pays on time' forecasting. It's probability-weighted. We expect $285,000 in the next 30 days, not the $432,000 total outstanding."

---

## Running the Project

### Prerequisites
- Docker Desktop running
- OpenAI API key

### Start Everything
```bash
cd predictive-analyzer-collection
docker-compose up -d
```

### Access
| Service | URL |
|---|---|
| Frontend | http://localhost:3002 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| ML Service | http://localhost:8001 |

### Set OpenAI API Key
Edit `backend/.env`:
```
OPENAI_API_KEY=sk-your-real-key-here
```
Then: `docker-compose up -d --no-deps --force-recreate backend`

### Train ML Models
```bash
docker exec ai-collector-ml-service python training/train_payment.py
docker exec ai-collector-ml-service python training/train_risk.py
docker restart ai-collector-ml-service
```

---

*Document generated: AI Collector v1.0 — Hackathon Build*  
*Architecture: Monorepo — frontend / backend / ml-service / docs*  
*AI: GPT-4o with OpenAI Function Calling (ReAct pattern)*
