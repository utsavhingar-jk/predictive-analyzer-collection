"""
AI Collector — FastAPI Application Entry Point.

Registers all routers, configures CORS, adds health check endpoint,
and initialises database tables on startup.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import forecast, invoices, predict, prioritize, recommend
from app.api.routes import behavior, delay, strategy, agent, borrower
from app.core.config import get_settings
from app.core.database import create_tables

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-native receivables optimization platform. "
        "Predicts payment probability, classifies risk, forecasts cashflow, "
        "prioritizes collections, and generates GPT-4o powered strategies."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────────────

app.include_router(predict.router)
app.include_router(forecast.router)
app.include_router(recommend.router)
app.include_router(invoices.router)
app.include_router(prioritize.router)
# Intelligence pipeline — new pillars
app.include_router(behavior.router)
app.include_router(delay.router)
app.include_router(strategy.router)
app.include_router(agent.router)
app.include_router(borrower.router)

# ─── Lifecycle ───────────────────────────────────────────────────────────────


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    try:
        create_tables()
        logger.info("Database tables verified.")
    except Exception as exc:
        logger.warning("Database init skipped (no DB connection): %s", exc)


# ─── Health Check ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["Health"])
def root() -> dict:
    return {"message": "AI Collector API", "docs": "/docs"}
