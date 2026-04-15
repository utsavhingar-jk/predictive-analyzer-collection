# AI Collector — Predictive Analytics Platform for Receivables

> **AI-native, agentic receivables optimization platform.** Predicts payment probability, forecasts cash flow, classifies risk, prioritizes collections, and generates GPT-4o powered collection strategies — all in one unified dashboard.

---

## Architecture Overview

```
predictive-analyzer-collection/
├── frontend/          React + Vite + TailwindCSS + ShadCN UI
├── backend/           Python FastAPI — orchestration & OpenAI agent
├── ml-service/        XGBoost / LightGBM training + SHAP inference service
├── shared/            Cross-service contracts and constants
├── docs/              Architecture docs and API reference
└── docker-compose.yml Full-stack local orchestration
```

---

## Features

| Feature | Description |
|---|---|
| Payment Prediction | P(pay in 7 / 15 / 30 days) per invoice |
| Risk Classification | High / Medium / Low risk via ML |
| Cash Flow Forecast | 7-day and 30-day inflow forecast |
| DSO Prediction | Days Sales Outstanding prediction |
| Collection Prioritization | Priority = amount × delay_probability |
| AI Recommendation | GPT-4o prescriptive collection actions |
| What-If Simulator | Scenario impact on recovery / cashflow / DSO |
| SHAP Explainability | Feature-level explanations per prediction |

---

## Quick Start (Docker)

### 1. Clone & configure environment

```bash
cp backend/.env.example backend/.env
cp ml-service/.env.example ml-service/.env
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` and add your **OpenAI API key**:
```
OPENAI_API_KEY=sk-...
```

### 2. Train ML models (first-time setup)

```bash
docker compose run --rm ml-service python training/train_payment.py
docker compose run --rm ml-service python training/train_risk.py
```

### 3. Start all services

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| ML Service | http://localhost:8001 |

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # fill in OPENAI_API_KEY + DATABASE_URL
uvicorn app.main:app --reload --port 8000
```

### ML Service

```bash
cd ml-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Train models first
python training/train_payment.py
python training/train_risk.py
# Start inference server
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# Opens at http://localhost:5173
```

---

## API Reference

See [`docs/api-reference.md`](docs/api-reference.md) for full endpoint docs.

Key endpoints:
- `POST /predict/payment` — Payment probability predictions
- `POST /predict/risk` — Risk classification + score
- `GET  /forecast/cashflow` — 7 / 30 day cashflow forecast
- `GET  /predict/dso` — Predicted DSO
- `GET  /prioritize/invoices` — Priority-sorted invoice worklist
- `POST /recommend/action` — GPT-4o collection recommendation
- `POST /whatif/simulate` — What-if scenario simulation

---

## Team

| Role | Focus |
|---|---|
| Data Scientist | ML pipeline (XGBoost, LightGBM, SHAP) in `ml-service/` |
| Full-stack Dev 1 | FastAPI backend, OpenAI agent in `backend/` |
| Full-stack Dev 2 | React dashboard pages + routing in `frontend/` |
| Full-stack Dev 3 | Charts, UI components, scenario simulator in `frontend/` |

---

## Tech Stack

- **Frontend**: React 18, Vite, TailwindCSS, ShadCN UI, Recharts
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2, Pydantic v2
- **ML**: XGBoost, LightGBM, SHAP, scikit-learn, pandas
- **AI**: OpenAI GPT-4o via `openai` Python SDK
- **Database**: PostgreSQL 16
- **Infra**: Docker, Docker Compose

---

## Environment Variables

### backend/.env

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_collector
ML_SERVICE_URL=http://localhost:8001
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
SECRET_KEY=change-me-in-production
```

### ml-service/.env

```
MODEL_DIR=serialized_models
DATASET_PATH=datasets/invoices.csv
```

### frontend/.env.local

```
VITE_API_BASE_URL=http://localhost:8000
```
