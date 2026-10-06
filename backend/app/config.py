"""Validated configuration; environment variables override the local .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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
    # Demo only: makes one endpoint slow and flaky so the dashboard has a problem to show.
    # The names are the keys of DEFAULT_PROFILES; a test keeps the two lists in step.
    simulation_degraded_endpoint: (
        Literal["users", "products", "orders", "search", "reports", "orders_create"] | None
    ) = None
    # "fake" gives a fixed, labelled answer without a key, for local demos; never in production.
    ai_provider: Literal["disabled", "fake", "gemini", "groq"] = "disabled"
    ai_api_key: SecretStr = SecretStr("")
    # Empty means the provider's default model. Part of a URL path for Gemini, so kept plain:
    # at most one "/" and no segment starting with ".", which rules out "..".
    ai_model: str = Field(
        default="",
        pattern=r"^([A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9_-][A-Za-z0-9._-]*)?)?$",
        max_length=100,
    )
    ai_timeout_seconds: float = Field(default=30, gt=0, le=120)
    # The same window within this many seconds reuses the last answer; 0 turns caching off.
    ai_cache_seconds: int = Field(default=60, ge=0, le=3600)
    # Real provider calls allowed in any rolling hour, across all clients.
    ai_quota_per_hour: int = Field(default=30, ge=1, le=1000)

    @model_validator(mode="after")
    def ai_settings_are_usable(self) -> Self:
        # Fail at startup, not at the first analysis request.
        if self.ai_provider in ("gemini", "groq") and not self.ai_api_key.get_secret_value():
            raise ValueError(f"AI_PROVIDER={self.ai_provider} needs AI_API_KEY.")
        if self.ai_provider == "fake" and self.environment == "production":
            raise ValueError(
                "AI_PROVIDER=fake gives invented answers and is not allowed in production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
