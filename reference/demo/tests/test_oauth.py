from __future__ import annotations

import time

import httpx
import pytest
import respx

from clario.zoho.errors import ZohoAuthError
from clario.zoho.oauth import TokenSet, TokenStore, ZohoOAuth


def test_authorization_url_contains_readonly_scopes(settings):
    oauth = ZohoOAuth(settings)
    url, state = oauth.authorization_url()
    assert "accounts.zoho.in/oauth/v2/auth" in url
    assert "response_type=code" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "ZohoBooks.invoices.READ" in url
    assert "CREATE" not in url
    assert state
    assert "client_secret" not in url


@pytest.mark.asyncio
async def test_exchange_code_stores_tokens(settings, tmp_path):
    store = TokenStore(tmp_path / "tokens.json", "")
    oauth = ZohoOAuth(settings, store)
    with respx.mock(assert_all_called=True) as router:
        router.post("https://accounts.zoho.in/oauth/v2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "api_domain": "https://www.zohoapis.in",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )
        tokens = await oauth.exchange_code("auth-code")
    assert tokens.access_token == "access-1"
    assert tokens.refresh_token == "refresh-1"
    loaded = store.load()
    assert loaded is not None
    assert loaded.refresh_token == "refresh-1"


@pytest.mark.asyncio
async def test_refresh_access_token(settings, tmp_path):
    store = TokenStore(tmp_path / "tokens.json", "refresh-1")
    store.save(
        TokenSet(
            access_token="old",
            refresh_token="refresh-1",
            expires_at=time.time() - 10,
        )
    )
    oauth = ZohoOAuth(settings, store)
    with respx.mock(assert_all_called=True) as router:
        router.post("https://accounts.zoho.in/oauth/v2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "access-2",
                    "api_domain": "https://www.zohoapis.in",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )
        tokens = await oauth.refresh_access_token()
    assert tokens.access_token == "access-2"
    assert tokens.refresh_token == "refresh-1"


@pytest.mark.asyncio
async def test_invalid_token_raises(settings, tmp_path):
    oauth = ZohoOAuth(settings, TokenStore(tmp_path / "tokens.json", "refresh-1"))
    with respx.mock(assert_all_called=True) as router:
        router.post("https://accounts.zoho.in/oauth/v2/token").mock(
            return_value=httpx.Response(200, json={"error": "invalid_code"})
        )
        with pytest.raises(ZohoAuthError, match="invalid_code"):
            await oauth.refresh_access_token()
