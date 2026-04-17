# AI Collector — Product Context (Final)

> **Audience:** Product managers, stakeholders, GTM, and leadership  
> **Purpose:** Single source of truth for what the platform does, how it maps to business objectives, what is “real” vs demo data, and how to talk about it externally.  
> **Last updated:** April 2026 · **Build:** AI Collector (hackathon / CredServ track)

---

## 1. Product vision

**AI Collector** is an intelligent receivables optimization platform for B2B finance and collections. It is **not** a passive AR dashboard. It is a **decision system** that:

- **Predicts** payment timing, delay probability, and default risks before write-offs grow using live XGBoost and LightGBM models.
- **Profiles** borrower payment behavior (not only credit score).
- **Prioritizes** collector effort by risk-weighted value.
- **Recommends** concrete actions, channels, and SLAs via GPT-4o agent.
- **Forecasts** probability-weighted cash inflows (7-day and 30-day horizons) across the entire portfolio.
- **Explains** reasoning via ML drivers + an optional **GPT-4o agent** with visible tool traces that understands both invoice-level AND portfolio-level queries.
- **Augments** predictions with **external-style signals** (Sentinel) and **borrower enrichment** (CredCheck-style).

---

## 2. Official objectives & deliverables (evaluation mapping)

| Objective / deliverable | What “done” means in product terms | Where it lives in the product |
|-------------------------|-----------------------------------|-------------------------------|
| **Payment default / delay probability** | Delay/Default probability + risk tier + drivers | Delay/Default prediction models, Invoice sidebar |
| **Payment behavior** | Borrower “personality” | Payment behavior card, worklist badges, agent tools |
| **Collection prioritization** | Ranked queue: who to work first | **Collector Worklist** (`/worklist`) — portfolio strategy API |
| **Cash flow forecasting** | Expected 7d / 30d inflows, amount at risk | **Executive Dashboard** — cashflow chart & KPIs |
| **DSO prediction** | Predicted vs current DSO, trend | Executive Dashboard metrics |
| **Payment prediction engine (7 / 15 / 30 days)** | Probabilities of payment within horizons | Invoice Detail sidebar — payment probability bars; `POST /predict/payment` |
| **Invoice-level Risk Labeling** | Risk label + score | Risk badges, `POST /predict/risk` |
| **Collections optimization** | Priority score, urgency, recommended action | Strategy card, worklist; `POST /optimize/collection-strategy`, portfolio strategy |
| **Prescriptive analytics** | Recommended action + timeline + reasoning | Agent recommendations block on Invoice Detail |
| **What-if scenario analysis** | Simulation of recovery impact | **Scenario Simulator** (`/simulator`) |

---

## 3. Mock data vs real engines (clearing confusion)

**Question:** *“Are we only solving the problem with mock data?”*

**Answer:** **No.** Mock data supplies **raw invoices**. The entire machine learning and AI inference layers are dynamically generated based on live engines. The Agent layer was recently decoupled from mocks entirely and generates real insights from Live ML Inference results:

| Layer | Role | Mock or real? |
|-------|------|----------------|
| **Payment model (XGBoost)** | 7/15/30 payment probabilities | **Real trained models** (`train_payment.py`) |
| **Default model (XGBoost)** | Absolute default risk after 30 days | **Real trained models** (`train_default.py`) |
| **Risk model (LightGBM)** | High / Medium / Low | **Real trained model** (`train_risk.py`) |
| **Delay prediction** | Delay prob + tier + drivers | **Real trained models** |
| **Agent AI Fusion** | GPT-4o analysis of Invoice AND Portfolio | **Real GPT-4o** connected via dynamic tool calls fetching live portfolio intelligence (no mocks). |

---

## 4. Problem we are solving

Instead of relying solely on aging buckets (DPD) to drive collections, the AI Collector uses predictive machine learning to surface high-risk invoices BEFORE they completely default. We fuse raw behavior models with live LLM processing to tell agents not only *who* is likely to default, but *why* and *what* they should explicitly do about it.

---

## 5. What makes this AI-native

1. **Predictive** — Machine Learning pipelines process 7/15/30 day delays and complete Default risks.
2. **Behavior-aware** — Uses payment personality features, not only baseline credit scores.
3. **Agentic** — A GPT-4o Agent with an autonomous toolkit handles free-text analysis over the entire portfolio.
4. **Hybrid** — Perfect alignment between ML boosting models, deterministic rules, and the language synthesis of modern LLMs.

---

## 6. User journey — screen by screen

### Executive Dashboard (`/`)
- A beautiful, premium visual interface designed using modern asymmetric grid placements and soft gradients.
- Showcases live KPIs: portfolio at risk, expected cash flows, dynamic AI priority worklists.
- Hover states and micro-animations to highlight dynamic data capabilities natively.

### Collector Worklist (`/worklist`)
- Predictive queue sorted efficiently by Risk Tier and Delay Probability vs plain DPD.

### Invoice detail (`/invoices/:id`) — The 2-Column Asymmetric View
We eliminated multi-tab clutter in favor of a sleek, singular dashboard view scaling beautifully across devices.
| Column | Content |
|-----|---------|
| **Main Content (Left 2/3)** | Invoice core details, Agent Collection Responses (SLA + rationale), Interaction timelines. |
| **Deep Analytics (Right 1/3)** | Payment horizon percentages (7/15/30), Advanced Default Predictions, Behavior Risk Metrics, and Explainability Panels. |

### Scenario Simulator (`/simulator`)
- What-if sliders determining recovery efficiencies based on operational speed and discounts.

---

## 7. Tech stack

| Layer | Stack |
|-------|--------|
| Frontend | React 18, Vite, React Router, Tailwind CSS (premium interactions), shadcn-style UI |
| Backend | Python 3.11, FastAPI, Pydantic v2, httpx, OpenAI SDK |
| ML | FastAPI, XGBoost, LightGBM, scikit-learn, SHAP frameworks |
| Infra | Docker Compose |

---

## 8. Running the project

```bash
docker compose build --no-cache frontend
docker compose up -d
docker compose restart backend ml-service
```

| URL | Service |
|-----|---------|
| http://localhost:3002 | Frontend Dashboard |
| http://localhost:8000/docs | Backend API Docs |
| http://localhost:8001 | ML Service |
