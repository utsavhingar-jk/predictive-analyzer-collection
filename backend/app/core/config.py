"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    APP_NAME: str = "AI Collector API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_collector"

    # ML Service
    ML_SERVICE_URL: str = "http://localhost:8001"

    # Borrower portfolio (GET /predict/borrowers/portfolio)
    BORROWER_PORTFOLIO_MAX_WORKERS: int = 8
    # Blend ML service output with backend rule engine: 0 = rules only, 1 = ML only, 0.5 = equal mix
    BORROWER_PORTFOLIO_HYBRID_ML_WEIGHT: float = 0.5

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:5173",
    ]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
