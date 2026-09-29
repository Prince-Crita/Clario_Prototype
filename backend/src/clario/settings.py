"""Typed application settings (FINAL_ARCHITECTURE_PLAN.md §39).

Loaded from the repository-root `.env`, then `.env.local` (overrides), then real environment
variables (highest precedence). Secrets are `SecretStr` so they never appear in reprs or logs.
The app refuses to start with missing or weak security settings.
"""

from __future__ import annotations

import base64
import binascii
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


ZohoRegion = Literal["in", "com", "eu", "au", "jp", "ca"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App
    app_env: AppEnv = AppEnv.DEVELOPMENT
    app_base_url: str = "http://localhost:5173"
    log_level: str = "INFO"
    log_format: Literal["auto", "json", "console"] = "auto"

    # --- Database
    database_url: str
    test_database_url: str | None = None
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    # --- Sessions & encryption
    session_secret: SecretStr
    session_idle_hours: int = Field(default=12, ge=1)
    session_absolute_days: int = Field(default=7, ge=1)
    session_cookie_secure: bool = False
    encryption_keys: SecretStr

    # --- AI (plan §20): one provider at a time, chosen here; the assistant never knows which
    llm_provider: Literal["groq", "openrouter"] = "groq"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-120b"
    openrouter_api_key: SecretStr | None = None
    # Free, tool-calling model for development; openai/gpt-oss-120b (the evaluated model) needs
    # OpenRouter credits.
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    llm_timeout_seconds: float = Field(default=30, gt=0)
    llm_max_tool_rounds: int = Field(default=6, ge=1, le=12)

    # --- Zoho Books (Crita's server-based application; plan §16–17)
    zoho_client_id: str = ""
    zoho_client_secret: SecretStr = SecretStr("")
    zoho_redirect_uri: str = "http://localhost:5173/api/v1/oauth/zoho-books/callback"
    zoho_default_region: ZohoRegion = "in"
    zoho_scopes: str = ""
    zoho_requests_per_minute: int = Field(default=60, ge=1)
    zoho_max_pages: int = Field(default=100, ge=1)

    # --- Finance data mirror (plan §31)
    finance_stale_after_minutes: int = Field(default=15, ge=1)
    finance_refresh_cooldown_seconds: int = Field(default=60, ge=0)
    finance_fixture_source: bool = False
    # golden = the director PDFs' real amounts (dashboard checks); evaluation = synthetic TEST
    # figures, the only fixture safe to send to the AI provider before its data terms are agreed.
    finance_fixture_dataset: Literal["golden", "evaluation"] = "golden"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _asyncpg_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "must be a PostgreSQL URL using the asyncpg driver (postgresql+asyncpg://…)"
            )
        return value

    @field_validator("session_secret")
    @classmethod
    def _strong_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")
        return value

    @field_validator("encryption_keys")
    @classmethod
    def _valid_fernet_keys(cls, value: SecretStr) -> SecretStr:
        keys = [k.strip() for k in value.get_secret_value().split(",") if k.strip()]
        if not keys:
            raise ValueError("ENCRYPTION_KEYS must contain at least one Fernet key")
        for key in keys:
            try:
                if len(base64.urlsafe_b64decode(key.encode())) != 32:
                    raise ValueError
            except (binascii.Error, ValueError):
                raise ValueError("ENCRYPTION_KEYS contains an invalid Fernet key") from None
        return value

    @model_validator(mode="after")
    def _production_rules(self) -> Self:
        if self.app_env is AppEnv.PRODUCTION:
            problems = []
            if not self.session_cookie_secure:
                problems.append("SESSION_COOKIE_SECURE must be true")
            if self.finance_fixture_source:
                problems.append("FINANCE_FIXTURE_SOURCE must be false")
            if not self.app_base_url.startswith("https://"):
                problems.append("APP_BASE_URL must use https")
            if problems:
                raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    # --- Derived values
    @property
    def fernet_keys(self) -> list[str]:
        return [k.strip() for k in self.encryption_keys.get_secret_value().split(",") if k.strip()]

    @property
    def zoho_scope_list(self) -> list[str]:
        return [s.strip() for s in self.zoho_scopes.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION

    @property
    def effective_log_format(self) -> Literal["json", "console"]:
        if self.log_format == "auto":
            return "json" if self.is_production else "console"
        return self.log_format


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings. Tests construct `Settings(...)` directly instead."""
    return Settings()  # required values come from .env / the environment
