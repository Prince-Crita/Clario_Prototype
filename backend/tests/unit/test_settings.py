from __future__ import annotations

import pytest
from pydantic import ValidationError

from clario.settings import AppEnv
from tests.support import make_settings


def test_valid_settings_hide_secrets_in_repr() -> None:
    settings = make_settings()
    assert "sss" not in repr(settings)
    assert settings.session_secret.get_secret_value() == "s" * 48
    assert len(settings.fernet_keys) == 1


def test_rejects_short_session_secret() -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        make_settings(session_secret="too-short")


@pytest.mark.parametrize("keys", ["", "not-a-key", "YWJj"])
def test_rejects_invalid_encryption_keys(keys: str) -> None:
    with pytest.raises(ValidationError, match="ENCRYPTION_KEYS"):
        make_settings(encryption_keys=keys)


def test_accepts_a_providers_postgres_url_and_normalises_it_for_asyncpg() -> None:
    # The URL as Neon issues it: libpq's scheme, sslmode and channel_binding.
    settings = make_settings(
        database_url="postgresql://u:p@ep-x-pooler.c-4.aws.neon.tech/db?sslmode=require&channel_binding=require",
        database_url_unpooled="",  # empty means "not set"
    )
    assert settings.database_url.startswith("postgresql+asyncpg://u:p@ep-x-pooler.")
    assert "ssl=require" in settings.database_url
    assert "channel_binding" not in settings.database_url
    assert settings.database_url_unpooled is None
    # Migrations go to the direct endpoint, derived from the pooled one.
    assert "@ep-x.c-4.aws.neon.tech/" in settings.migration_database_url


def test_rejects_a_non_postgres_database_url_without_echoing_it() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL URL") as exc:
        make_settings(database_url="mysql://user:hunter2@localhost/db")
    assert "hunter2" not in str(exc.value)  # secrets never appear in a validation error


def test_production_requires_safe_configuration() -> None:
    with pytest.raises(ValidationError) as exc:
        make_settings(app_env=AppEnv.PRODUCTION, finance_fixture_source=True)
    message = str(exc.value)
    assert "SESSION_COOKIE_SECURE" in message
    assert "FINANCE_FIXTURE_SOURCE" in message
    assert "https" in message


def test_production_accepts_safe_configuration() -> None:
    settings = make_settings(
        app_env=AppEnv.PRODUCTION, session_cookie_secure=True, app_base_url="https://clario.example"
    )
    assert settings.is_production
    assert settings.effective_log_format == "json"


def test_scope_list_parsing() -> None:
    settings = make_settings(zoho_scopes="ZohoBooks.invoices.READ, ZohoBooks.reports.READ,,")
    assert settings.zoho_scope_list == ["ZohoBooks.invoices.READ", "ZohoBooks.reports.READ"]
