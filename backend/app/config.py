"""Validated configuration; environment variables override the local .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "API Performance Dashboard"
    environment: Literal["development", "test", "production"] = "development"
    db_host: str = "127.0.0.1"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "performance_dashboard"
    test_db_name: str = "performance_dashboard_test"
    db_user: str = "dashboard"
    db_password: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:5173"]
    metrics_window_minutes: int = Field(default=60, ge=1, le=1440)
    simulation_latency_scale: float = Field(default=1.0, ge=0, le=100)
    simulation_failure_scale: float = Field(default=1.0, ge=0, le=100)
    ai_provider: Literal["disabled", "gemini", "groq"] = "disabled"
    ai_api_key: SecretStr = SecretStr("")
    ai_model: str = ""
    ai_timeout_seconds: float = Field(default=30, gt=0, le=120)


@lru_cache
def get_settings() -> Settings:
    return Settings()
