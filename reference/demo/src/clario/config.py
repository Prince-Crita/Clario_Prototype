"""Environment-driven configuration. Secrets never belong in source or the frontend."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SCOPES = (
    "ZohoBooks.invoices.READ",
    "ZohoBooks.contacts.READ",
    "ZohoBooks.settings.READ",
    "ZohoBooks.expenses.READ",
    "ZohoBooks.customerpayments.READ",
    "ZohoBooks.accountants.READ",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_redirect_uri: str = "http://localhost:8000/oauth/zoho/callback"
    zoho_accounts_url: str = "https://accounts.zoho.in"
    zoho_api_base_url: str = "https://www.zohoapis.in/books/v3"
    zoho_organization_id: str = ""
    zoho_refresh_token: str = ""
    zoho_scopes: str = ",".join(DEFAULT_SCOPES)

    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # LLM provider: groq (default) or gemini
    llm_provider: str = "groq"
    groq_api_key: str = ""
    # LiteLLM model id — see https://docs.groq.com/docs/models
    groq_model: str = "groq/openai/gpt-oss-120b"

    clario_host: str = "127.0.0.1"
    clario_port: int = 8000
    clario_log_level: str = "INFO"
    clario_data_dir: Path = Field(default=PROJECT_ROOT / ".data")

    # Multi-tenant database. Use PostgreSQL in production.
    # Local default: sqlite+aiosqlite:///<data_dir>/clario.db
    database_url: str = ""
    # Fernet key for encrypting Zoho tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    clario_encryption_key: str = ""
    # JWT signing secret for user sessions
    clario_jwt_secret: str = "change-me-in-production"
    clario_jwt_hours: int = 72
    # When true, prefer DB-backed tenants over the legacy single-org .env path
    multi_tenant_enabled: bool = True

    request_timeout_seconds: float = 30.0
    max_retries: int = 3
    max_pages: int = 20
    per_page: int = 200
    date_range_max_days: int = 366

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = (self.clario_data_dir / "clario.db").resolve()
        return f"sqlite+aiosqlite:///{db_path}"

    @field_validator("zoho_accounts_url", "zoho_api_base_url", "zoho_redirect_uri")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def scopes(self) -> list[str]:
        return [item.strip() for item in self.zoho_scopes.split(",") if item.strip()]

    @property
    def token_path(self) -> Path:
        return self.clario_data_dir / "zoho_tokens.json"

    def require_zoho_oauth_app(self) -> None:
        missing = [
            name
            for name, value in (
                ("ZOHO_CLIENT_ID", self.zoho_client_id),
                ("ZOHO_CLIENT_SECRET", self.zoho_client_secret),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing Zoho OAuth app credentials: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill in the Zoho Developer Console values."
            )

    def zoho_ready(self) -> bool:
        return bool(
            self.zoho_client_id
            and self.zoho_client_secret
            and (self.zoho_refresh_token or self.token_path.exists())
        )

    def llm_ready(self) -> bool:
        provider = self.llm_provider.strip().lower()
        if provider == "groq":
            return bool(self.groq_api_key)
        if provider == "gemini":
            return bool(self.google_api_key)
        return False

    def llm_label(self) -> str:
        provider = self.llm_provider.strip().lower()
        if provider == "groq":
            return self.groq_model
        return self.gemini_model


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.clario_data_dir.mkdir(parents=True, exist_ok=True)
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
