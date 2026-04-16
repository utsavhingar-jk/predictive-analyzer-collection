# AI Collector — Product Context (Final)

> **Audience:** Product managers, stakeholders, GTM, and leadership  
> **Purpose:** Single source of truth for what the platform does, how it maps to business objectives, what is “real” vs demo data, and how to talk about it externally.  
> **Last updated:** April 2026 · **Build:** AI Collector (hackathon / CredServ track)

---

## Table of Contents

1. [Product vision](#1-product-vision)
2. [Official objectives & deliverables (evaluation mapping)](#2-official-objectives--deliverables-evaluation-mapping)
3. [Mock data vs real engines (clearing confusion)](#3-mock-data-vs-real-engines-clearing-confusion)
4. [Problem we are solving](#4-problem-we-are-solving)
5. [What makes this AI-native](#5-what-makes-this-ai-native)
6. [User personas](#6-user-personas)
7. [The five intelligence pillars + agent–ML fusion](#7-the-five-intelligence-pillars--agentml-fusion)
8. [Extended capabilities (Sentinel, enrichment, history)](#8-extended-capabilities-sentinel-enrichment-history)
9. [User journey — screen by screen](#9-user-journey--screen-by-screen)
10. [Agentic AI — how it works](#10-agentic-ai--how-it-works)
11. [Tech stack](#11-tech-stack)
12. [System architecture](#12-system-architecture)
13. [API overview](#13-api-overview)
14. [Data & persistence](#14-data--persistence)
15. [ML models & explainability](#15-ml-models--explainability)
16. [Current state vs production path](#16-current-state-vs-production-path)
17. [Team workstreams](#17-team-workstreams)
18. [Demo script](#18-demo-script)
19. [Running the project](#19-running-the-project)

---

## 1. Product vision

**AI Collector** is an intelligent receivables optimization platform for B2B finance and collections. It is **not** a passive AR dashboard. It is a **decision system** that:

- **Predicts** payment timing and delay risk before write-offs grow
- **Profiles** borrower payment behavior (not only credit score)
- **Prioritizes** collector effort by risk-weighted value
- **Recommends** concrete actions, channels, and SLAs
- **Forecasts** probability-weighted cash inflows (7-day and 30-day horizons)
- **Explains** reasoning via ML drivers + an optional **GPT-4o agent** with visible tool traces
- **Augments** predictions with **external-style signals** (Sentinel) and **borrower enrichment** (CredCheck-style), where integrated or simulated for demo

**Currency & market:** Demo data is **INR**-oriented; the architecture applies globally (localize currency, credit bureaus, and regulations).

---

## 2. Official objectives & deliverables (evaluation mapping)

Below is how the **stated hackathon / business objectives** map to **shipped product capabilities**. Use this table when aligning with leadership or judges.

| Objective / deliverable | What “done” means in product terms | Where it lives in the product |
|-------------------------|-----------------------------------|-------------------------------|
| **Payment default / delay probability** | Per-invoice delay probability + risk tier + drivers | Delay prediction on invoice (Intelligence tab), worklist columns |
| **Payment behavior** | Borrower “personality” (e.g. chronic late payer, reminder-driven) | Payment behavior card, worklist badges, agent tools |
| **Collection prioritization** | Ranked queue: who to work first | **Collector Worklist** (`/worklist`) — portfolio strategy API |
| **Cash flow forecasting** | Expected 7d / 30d inflows, amount at risk, shortfall signal | **Executive Dashboard** — cashflow chart & KPIs |
| **DSO prediction** | Predicted vs current DSO, trend | Executive Dashboard metrics |
| **Payment prediction engine (7 / 15 / 30 days)** | Probabilities of payment within horizons | Invoice **Overview** tab — payment probability bars; `POST /predict/payment` |
| **Invoice-level late payment risk (High / Medium / Low)** | Risk label + score | Risk badges, risk pie chart, `POST /predict/risk` |
| **Collections optimization** | Priority score, urgency, recommended action, optional **candidate actions** + selection rationale | Strategy card, worklist; `POST /optimize/collection-strategy`, portfolio strategy |
| **Prescriptive analytics (exact actions)** | Recommended action + timeline + reasoning | Next action on Overview; OpenAI recommendation API; full **agent** analysis |
| **What-if scenario analysis** | Sliders changing recovery / discount / follow-up delay → impact on recovery, cashflow, DSO | **Scenario Simulator** (`/simulator`) |
| **Technologies: boosting, SHAP, etc.** | XGBoost (payment), LightGBM (risk), SHAP module in ML service; delay uses ML service + rule fallback | `ml-service/` |

**Bonus topics (discussion, not fully automated in repo):**

- **eNACH / CredServ onboarding** — Product/process journey (30-day setup); UI may **surface NACH recommendations** from behavior/strategy, not full mandate workflow.
- **CredCheck consent journey** — Enrichment UI shows **data availability flags** and simulated MCA/GST/bureau signals; production needs consent orchestration and vendor APIs.

---

## 3. Mock data vs real engines (clearing confusion)

**Question:** *“Are we only solving the problem with mock data?”*

**Answer:** **No.** Mock data supplies **sample invoices and customers** so the demo runs without your ERP. The **solution** is the **pipeline of engines + APIs + UX**:

| Layer | Role | Mock or real? |
|-------|------|----------------|
| **Invoice / customer master** | Rows to score | **Mock** in `backend/app/utils/mock_data.py` (15 INR invoices, Indian names) — **replace with DB/API** in production |
| **Payment model (XGBoost)** | 7/15/30 payment probabilities | **Real trained models** in `ml-service/serialized_models/` (trained on synthetic INR CSV) |
| **Risk model (LightGBM)** | High / Medium / Low | **Real trained model** |
| **Delay prediction** | Delay prob + tier + drivers | **ML service** + **backend rule fallback** if ML confidence low or service down |
| **Behavior classification** | Behavior type, trend | **Rule engine** today; **placeholder** for future behavior ML |
| **Strategy / prioritization** | Priority score, actions | **Deterministic optimization layer** (rules + scoring) |
| **Cashflow / DSO** | Portfolio metrics | **Computed** from the same invoice set (mock or real) |
| **OpenAI agent** | Tool-calling + narrative | **Real GPT-4o** when API key set; **rule fallback** if OpenAI unavailable |
| **Sentinel / CredCheck-style enrichment** | External risk + compliance signals | **Simulated** per customer for demo — **replace with APIs** (news, MCA, GST, bureau) |
| **Interaction history** | Calls, PTP, outcomes | **Mock timeline** — **replace with** `collection_feedback` / CRM data |
| **Agent–ML fusion** | Blend ML delay with Sentinel + enrichment + history | **Real logic** on backend after agent case analysis |
| **PostgreSQL** | System of record | **Configured** (`DATABASE_URL`); **not** wired as primary read path for invoices in current demo — schema exists in `docs/database-schema.sql` |

**One-liner for slides:**  
*“Demo data feeds the same engines production would use — swap the ledger, keep the stack.”*

---

## 4. Problem we are solving

### Traditional collections pain

| Pain | Reality |
|------|---------|
| Worklists by age bucket only | High **amount × delay risk** cases may rank below noisy low-risk large balances |
| No borrower-level view | Relationship exposure and behavior are invisible |
| Cash forecasts are optimistic | Finance assumes collections; we use **probability-weighted** expectations |
| Escalation is gut-feel | System recommends **action + SLA** from unified scores |
| Static follow-up cadence | Behavior and risk drive **urgency** |

### What changes with AI Collector

Instead of: *“INV-001 is 45 DPD → send reminder”*, the product supports: *“This invoice has high delay probability given **behavior + amount + history**; priority 95/100; **call + NACH within 2h**; agent explains why.”*

---

## 5. What makes this AI-native

1. **Predictive** — Scores future delay and payment horizons, not only past DPD.
2. **Behavior-aware** — Uses payment personality features, not only credit score.
3. **Agentic (optional)** — GPT-4o runs a **ReAct loop** with **function calling**: it chooses which tools to run and in what order; the UI shows a **reasoning trace**.
4. **Hybrid** — Gradient boosting models + transparent rules + LLM; **not** only `if/then` disguised as AI.
5. **Fusion layer** — After a full case analysis, delay probability can be **fused** with Sentinel score, enrichment score, and interaction-history boost for a single **fused delay** story (see Intelligence tab).

---

## 6. User personas

| Persona | Goal | Primary surfaces |
|---------|------|------------------|
| **Collections manager / lead** | Portfolio risk, shortfall, who to escalate | Executive Dashboard, Borrower Portfolio, Watchlist |
| **Collector** | Ordered worklist, what to do on one invoice | Worklist, Invoice (Overview + Intelligence + Agent tabs) |
| **Credit / risk analyst** | Borrower-level exposure and signals | Borrower Portfolio, enrichment + Sentinel on invoice |
| **CFO / finance** | Cash timing, DSO, what-if | Dashboard, Scenario Simulator |

---

## 7. The five intelligence pillars + agent–ML fusion

Logical pipeline (outputs feed forward):

```
[1] Payment behavior  →  [2] Delay prediction  →  [3] Collection strategy
         ↓                        ↓                        ↓
[4] Cash flow forecast  ←  portfolio predictions
         ↓
[5] Agentic layer (GPT-4o + tools + trace)
         ↓
[+] Agent–ML fusion (optional): ML/reason delay + Sentinel + CredCheck-style score + history → fused delay + explainable delta
```

- **Pillar 1 — Behavior:** `POST /analyze/payment-behavior` — classifies payment style, trend, NACH hint.
- **Pillar 2 — Delay:** `POST /predict/delay` — delay probability, risk tier, drivers, confidence/evidence flags.
- **Pillar 3 — Strategy:** `POST /optimize/collection-strategy` — priority, urgency, recommended action; **candidate actions** with selection rationale where enabled.
- **Pillar 4 — Cashflow:** `GET /forecast/cashflow` — expected collections, at risk, shortfall.
- **Pillar 5 — Agent:** `POST /agent/analyze-case`, `POST /agent/ask` — tool-using agent with trace.

**Fusion (post–analyze-case):** The backend can adjust the **displayed delay probability** using sentinel + enrichment + interaction signals so product can say **“ML base vs fused”** on the delay card.

---

## 8. Extended capabilities (Sentinel, enrichment, history)

| Capability | User value | Implementation note |
|------------|------------|----------------------|
| **Sentinel (external signals)** | Leadership/news/AP/email-style flags | Mock per customer; watchlist page |
| **Borrower enrichment (CredCheck-style)** | MCA / GST / EPFO / bureau / legal hints | Mock profiles + **data availability flags** |
| **Interaction history** | Past touches, PTP, outcomes, **action effectiveness** | Mock timelines; feeds fusion boost |
| **Watchlist** | Portfolio of flagged external-risk customers | `/watchlist` |
| **Confidence layer** | Model confidence, evidence score, missing data, fallback | Shown on invoice Intelligence tab |

---

## 9. User journey — screen by screen

### Executive Dashboard (`/`)

- KPIs: total overdue, amount at risk, expected 30-day collections, high-risk counts, DSO, overdue carry-forward, **Critical + High** action count.
- Charts: cashflow forecast, risk mix.
- **Top priority cases:** Loaded from **live portfolio strategy API** (not a static mock list).

### Collector Worklist (`/worklist`)

- Ranked table: invoice, customer, amount, DPD, risk tier, **behavior badge**, priority score, delay %, urgency, recommended action.

### Borrower Portfolio (`/borrowers`)

- Borrower-level risk, exposure, recovery indicators; drawer for details.

### Sentinel Watchlist (`/watchlist`)

- Customers with elevated external signal scores; expandable signal detail.

### Invoice detail (`/invoices/:id`) — **three tabs** (reduced clutter)

| Tab | Content |
|-----|---------|
| **Overview** | Compact invoice facts, **payment 7/15/30** bars, **next action** (urgency + SLA + short reasoning) |
| **Intelligence** | Behavior, **delay** (including **agentic fusion** strip when present), strategy, borrower risk, confidence, **candidate actions** |
| **Agent & context** | Sentinel alert, **Run / Re-run analysis**, reasoning trace, interaction timeline, action effectiveness, enrichment card, **Ask the agent** |

### Scenario Simulator (`/simulator`)

- What-if sliders and impact on recovery / cashflow / DSO.

---

## 10. Agentic AI — how it works

### Properties

| Idea | Implementation |
|------|-----------------|
| Autonomy | Model chooses tools and order (within max iterations) |
| Tools | **Nine** backend-backed tools (function calling) |
| Trace | Each step stored for UI (`reasoning_trace`) |
| Fusion | After structured outputs, delay may be **fused** with Sentinel + enrichment + history |

### Tools (9)

| Tool | Purpose |
|------|---------|
| `get_invoice_details` | Load invoice facts |
| `analyze_payment_behavior` | Behavior profile |
| `predict_invoice_delay` | Delay + risk |
| `optimize_collection_strategy` | Strategy + candidates |
| `get_borrower_risk` | Portfolio-level borrower risk |
| `get_portfolio_summary` | Aggregate KPIs |
| `check_external_signals` | Sentinel-style signals |
| `get_interaction_history` | Touchpoints + effectiveness |
| `get_borrower_enrichment` | MCA/GST/bureau-style enrichment |

### Flow (simplified)

1. User runs **Analyze** on Agent tab → `POST /agent/analyze-case`.
2. GPT-4o loops: call tools → observe → repeat.
3. Response includes behavior, delay, strategy, summary, **trace**, and **fused delay** metadata when fusion runs.
4. **Ask** box → `POST /agent/ask` for free-form questions.

---

## 11. Tech stack

| Layer | Stack |
|-------|--------|
| Frontend | React 18, Vite, React Router, Tailwind, Radix/shadcn-style UI, Recharts |
| Backend | Python 3.11, FastAPI, Pydantic v2, httpx, OpenAI SDK |
| ML | FastAPI microservice, XGBoost, LightGBM, scikit-learn, SHAP helpers, pandas |
| Data | PostgreSQL available via Docker; **demo uses in-memory mocks unless you wire DB** |
| Infra | Docker Compose |

---

## 12. System architecture

```
Browser (React)
    → FastAPI backend :8000
        → ML service :8001 (payment, risk, delay, explain)
        → OpenAI API (agent, recommendations)
    → PostgreSQL (optional / future primary store)
```

Detailed diagrams: `docs/architecture.md`.

---

## 13. API overview

**Core predictions:** `POST /predict/payment`, `/predict/risk`, `/predict/delay`, `GET /predict/dso`, borrower prediction routes.

**Behavior:** `POST /analyze/payment-behavior`.

**Strategy:** `POST /optimize/collection-strategy`, `GET /optimize/portfolio-strategy`.

**Forecast:** `GET /forecast/cashflow`.

**Agent:** `POST /agent/analyze-case`, `POST /agent/ask`.

**Recommendations / what-if:** `POST /recommend/action`, `POST /whatif/scenario`.

**Signals & enrichment:** `GET /sentinel/check/{customer_id}`, `GET /sentinel/watchlist`, `GET /interactions/{invoice_id}`, `GET /enrichment/{customer_id}`.

**Invoices:** `GET /invoices`, `GET /invoices/{id}`.

Full detail: `docs/api-reference.md`, Swagger `/docs`.

---

## 14. Data & persistence

| Data | Where it lives today |
|------|---------------------|
| Demo invoices & customers | Python mocks (`mock_data.py`), INR |
| Interaction stories | `mock_interactions.py` |
| Sentinel / enrichment | Service-level mock DBs |
| **Trained ML artifacts** | `ml-service/serialized_models/*.pkl`, scalers, `meta.json` |
| **Optional fusion training log** | Env `AGENT_FUSION_TRAINING_LOG` → append **JSONL** for retraining experiments |
| **PostgreSQL** | Schema in `docs/database-schema.sql` — connect when replacing mocks |

**Important:** There is **no** full persistence of every agent run or prediction to Postgres in the default demo paths; that is a **production backlog** item.

---

## 15. ML models & explainability

| Asset | Role |
|-------|------|
| XGBoost | Payment horizons (7/15/30) |
| LightGBM | Risk tier |
| Delay | ML service endpoint + backend rules + confidence threshold / fallback |
| SHAP | Available via ML `/explain` for payment feature attribution; invoice shows **top drivers** on delay card |

Training scripts: `ml-service/training/train_payment.py`, `train_risk.py`. Dataset: `ml-service/datasets/invoices.csv` (INR, multi-row).

---

## 16. Current state vs production path

| Area | Now | Next |
|------|-----|------|
| Master data | Mock invoices | ERP / warehouse / `GET` invoices from DB |
| External data | Simulated Sentinel / enrichment | News, MCA, GST, bureau APIs + consent |
| History | Mock interactions | CRM + `collection_feedback` table |
| Auth | Open demo | SSO / JWT |
| Ops | Manual deploy | Monitoring, drift alerts, scheduled rescoring |

Integration notes: `docs/DATA_INTEGRATION_GUIDE.md`, `docs/db-connection-guide.md`.

---

## 17. Team workstreams

- **Data science:** Own `ml-service`, retrain on production data, calibrate delay and behavior models.
- **Backend:** DB-backed routes, auth, schedulers, vendor integrations.
- **Agent:** Tool expansion, guardrails, streaming responses.
- **Frontend:** UX polish, accessibility, mobile, notifications.

---

## 18. Demo script (updated)

1. **Dashboard** — Shortfall, expected 30-day cash, risk mix, top cases from API.
2. **Worklist** — Rank 1: why this invoice (priority, behavior, delay).
3. **Invoice → Overview** — Next action + payment bars in one screen.
4. **Invoice → Intelligence** — Behavior, delay (**fusion** if user ran agent), strategy, confidence.
5. **Invoice → Agent & context** — Run analysis → **trace**; optional Ask question; Sentinel + history + enrichment.
6. **Watchlist** — External-risk portfolio view.
7. **Simulator** — Move sliders → explain impact on recovery/DSO/cashflow.

---

## 19. Running the project

**Prerequisites:** Docker (recommended), OpenAI API key for agent.

```bash
cd predictive-analyzer-collection
docker compose up -d
```

| URL | Service |
|-----|---------|
| http://localhost:3002 | Frontend |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Swagger |
| http://localhost:8001 | ML service |

**OpenAI:** Set `OPENAI_API_KEY` in `backend/.env` and recreate the backend container.

**Retrain models (inside ml container):**

```bash
docker exec ai-collector-ml-service python training/train_payment.py
docker exec ai-collector-ml-service python training/train_risk.py
```

**Optional fusion log:** set `AGENT_FUSION_TRAINING_LOG=/path/to/fusion.jsonl` in backend env.

---

## Document control

| | |
|--|--|
| **Repository** | `predictive-analyzer-collection` (monorepo: `frontend/`, `backend/`, `ml-service/`, `docs/`) |
| **Primary product doc** | This file — share with product as **the** context doc |
| **Judge-facing deck** | `docs/judge-presentation.html` |

---

*End of document — AI Collector product context (final update for product stakeholders).*
