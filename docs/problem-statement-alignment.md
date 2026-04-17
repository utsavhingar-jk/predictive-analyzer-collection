# Utsav Problem Statement Alignment

This repository already maps closely to the **"Predictive Analytics for Collections"** problem statement. The platform is not just a dashboard; it already combines predictive modeling, prescriptive actions, portfolio prioritization, and scenario simulation for receivables teams.

## Objective Coverage

| Objective From Prompt | Current Coverage | Evidence in Repo |
|---|---|---|
| Forecast cash flows | Implemented | `backend/app/services/cashflow_service.py`, `backend/app/api/routes/forecast.py` |
| Predict payment behavior | Implemented | `backend/app/services/behavior_service.py`, `backend/app/api/routes/behavior.py` |
| Predict payment delays | Implemented | `backend/app/services/delay_service.py`, `backend/app/api/routes/delay.py` |
| Optimize collection strategies | Implemented | `backend/app/services/strategy_service.py`, `backend/app/api/routes/strategy.py` |

## Use Case Coverage

| Use Case | Status | Current Product Mapping |
|---|---|---|
| Payment default / delay probability prediction | Implemented | `POST /predict/payment`, `POST /predict/delay`, invoice detail risk cards |
| Collection prioritization | Implemented | `GET /prioritize/invoices`, `GET /optimize/portfolio-strategy`, `frontend/src/pages/CollectorWorklist.jsx` |
| Cash flow forecasting for businesses | Implemented | `GET /forecast/cashflow`, `frontend/src/pages/ExecutiveDashboard.jsx` |
| Days Sales Outstanding (DSO) prediction | Implemented | `GET /predict/dso`, dashboard KPI cards |

## Deliverable Coverage

| Deliverable | Status | How It Is Addressed |
|---|---|---|
| Payment prediction engine for next 7 / 15 / 30 days | Implemented | `ml-service/training/train_payment.py` trains horizon-specific XGBoost models surfaced through `POST /predict/payment` |
| Invoice-level late payment probability with High / Medium / Low risk | Implemented | `POST /predict/delay` returns delay probability and risk tier; `POST /predict/risk` provides explicit risk classification |
| Collections optimization algorithm to maximize recovery efficiency | Implemented | `backend/app/services/strategy_service.py` scores candidate actions, selects the best action, and ranks the portfolio |
| Prescriptive analytics engine to recommend exact actions | Implemented | `POST /optimize/collection-strategy` returns next-best actions; `POST /recommend/action` adds GPT-4o reasoning |
| What-if scenario analysis tool | Implemented | `POST /whatif/simulate` and `frontend/src/pages/ScenarioSimulator.jsx` model recovery, cashflow, and DSO impact |

## Technology Fit

| Prompt Technology | Current Status | Notes |
|---|---|---|
| XGBoost | Implemented | Primary training pipeline in `ml-service/training/train_payment.py` and `ml-service/training/train_risk.py` |
| LightGBM | Partial / legacy | Current inference still supports legacy LightGBM artifacts, but the active training path is XGBoost-first |
| CatBoost | Not yet implemented | Good next benchmark if the submission must explicitly show multiple gradient-boosting families |
| Neural networks | Not yet implemented | Optional next-step baseline, not required for current end-to-end workflow |
| SHAP explainability | Implemented | `ml-service/explainability/shap_explainer.py` and `/predict/explain` |
| Time-series forecasting | Partially implemented | Current cashflow forecasting is probability-weighted portfolio forecasting; a dedicated ARIMA / Prophet / LSTM layer would make the match even tighter |

## Best Submission Framing

If you are presenting this for judging, the strongest framing is:

1. Position it as an **end-to-end collections intelligence engine**, not just a prediction model.
2. Emphasize that it operates at both **invoice level** and **portfolio level**.
3. Call out the exact deliverables already present: 7 / 15 / 30 day payment probability, late-payment risk tiers, prioritization, prescriptive actions, and what-if analysis.
4. Be explicit that the current technical core is **XGBoost + SHAP + forecasting + GPT-powered recommendations**, with CatBoost and neural nets as optional next-stage benchmarks rather than missing business functionality.

## If You Want an Even Tighter Match

The current implementation is already strong enough to be presented as a solution to the prompt. If you want a more literal one-to-one technology match afterward, the next additions should be:

1. Add a CatBoost benchmark notebook and compare AUC / calibration against XGBoost.
2. Add a simple neural baseline for payment-delay or cashflow forecasting.
3. Introduce a dedicated time-series model for portfolio inflow forecasting alongside the current probability-weighted forecast engine.
