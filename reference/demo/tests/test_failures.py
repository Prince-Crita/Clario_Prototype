from __future__ import annotations

from datetime import date

import pytest

from clario.analytics.dates import parse_iso_date, validate_range
from clario.logging import redact, redact_mapping
from clario.zoho.oauth import TokenStore, ZohoOAuth


def test_invalid_date_rejected():
    with pytest.raises(ValueError, match="Invalid date"):
        parse_iso_date("09/22/2026")
    with pytest.raises(ValueError, match="end_date"):
        validate_range(date(2026, 9, 22), date(2026, 9, 1))


def test_secrets_are_redacted_in_logs():
    text = redact("Authorization: Zoho-oauthtoken 1000.supersecret.token")
    assert "supersecret" not in text
    mapping = redact_mapping({"refresh_token": "abc", "organization_id": "1"})
    assert mapping["refresh_token"] == "[REDACTED]"
    assert mapping["organization_id"] == "1"


def test_missing_oauth_app_credentials(tmp_path):
    from clario.config import Settings

    oauth = ZohoOAuth(
        Settings(clario_data_dir=tmp_path, zoho_client_id="", zoho_client_secret=""),
        TokenStore(tmp_path / "tokens.json"),
    )
    with pytest.raises(RuntimeError, match="ZOHO_CLIENT_ID"):
        oauth.authorization_url()
