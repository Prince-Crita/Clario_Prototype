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


def test_rejects_non_asyncpg_database_url() -> None:
    with pytest.raises(ValidationError, match="asyncpg"):
        make_settings(database_url="postgresql://u:p@localhost/db")


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
