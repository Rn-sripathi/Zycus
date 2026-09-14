"""Application configuration.

Single source of truth for environment and tunables. Nothing else in the codebase
calls os.getenv, so there is exactly one place to look when something is misconfigured.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Postgres (Neon). Empty means the app runs without persistence.
    database_url: str = ""
    database_pool_size: int = 5

    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    # Model self-reported confidence at or above this is eligible for MEDIUM
    # (auto-suggest). Below it, the finding is flagged for human review.
    confidence_threshold: float = 0.8

    @property
    def llm_enabled(self) -> bool:
        """False when no key is configured -- lets the deterministic layer run alone."""
        return bool(self.openai_api_key.strip())

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
