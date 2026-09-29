"""OAuth 2.0 for Zoho Books. Tokens are never returned to the frontend."""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from clario.config import Settings
from clario.logging import get_logger, redact_mapping
from clario.zoho.errors import ZohoAuthError, ZohoConfigError

logger = get_logger("clario.zoho.oauth")


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float
    api_domain: str | None = None
    token_type: str = "Bearer"

    @property
    def expired(self) -> bool:
        # Refresh one minute early to avoid using a token that expires mid-request.
        return time.time() >= (self.expires_at - 60)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "expires_at": self.expires_at,
            "api_domain": self.api_domain,
            "expired": self.expired,
        }


class TokenStoreProtocol(Protocol):
    def load(self) -> TokenSet | None: ...

    def save(self, tokens: TokenSet) -> None: ...

    def clear(self) -> None: ...


class TokenStore:
    """Persists refresh/access tokens on disk so OAuth does not have to be repeated."""

    def __init__(self, path: Path, env_refresh_token: str = "") -> None:
        self.path = path
        self.env_refresh_token = env_refresh_token

    def load(self) -> TokenSet | None:
        data: dict[str, Any] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
        refresh_token = data.get("refresh_token") or self.env_refresh_token
        access_token = data.get("access_token") or ""
        if not refresh_token and not access_token:
            return None
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token or None,
            expires_at=float(data.get("expires_at") or 0),
            api_domain=data.get("api_domain"),
            token_type=data.get("token_type") or "Bearer",
        )

    def save(self, tokens: TokenSet) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at,
            "api_domain": tokens.api_domain,
            "token_type": tokens.token_type,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.path.chmod(0o600)
        logger.info("Stored Zoho tokens at %s", self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class ZohoOAuth:
    def __init__(self, settings: Settings, store: TokenStoreProtocol | None = None) -> None:
        self.settings = settings
        self.store = store or TokenStore(settings.token_path, settings.zoho_refresh_token)
        self._tokens = self.store.load()

    def authorization_url(self, state: str | None = None) -> tuple[str, str]:
        self.settings.require_zoho_oauth_app()
        state = state or secrets.token_urlsafe(24)
        params = {
            "scope": ",".join(self.settings.scopes),
            "client_id": self.settings.zoho_client_id,
            "response_type": "code",
            "redirect_uri": self.settings.zoho_redirect_uri,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        url = f"{self.settings.zoho_accounts_url}/oauth/v2/auth?{urlencode(params)}"
        logger.info("Built Zoho authorization URL for redirect_uri=%s", self.settings.zoho_redirect_uri)
        return url, state

    async def exchange_code(self, code: str) -> TokenSet:
        self.settings.require_zoho_oauth_app()
        if not code:
            raise ZohoAuthError("Authorization code is missing.")
        data = await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": self.settings.zoho_client_id,
                "client_secret": self.settings.zoho_client_secret,
                "redirect_uri": self.settings.zoho_redirect_uri,
                "code": code,
            }
        )
        tokens = self._parse_token_response(data, previous=self._tokens)
        if not tokens.refresh_token:
            raise ZohoAuthError(
                "Zoho did not return a refresh token. Re-authorize with access_type=offline and prompt=consent."
            )
        self._tokens = tokens
        self.store.save(tokens)
        return tokens

    async def refresh_access_token(self, refresh_token: str | None = None) -> TokenSet:
        self.settings.require_zoho_oauth_app()
        token = refresh_token or (self._tokens.refresh_token if self._tokens else None) or self.settings.zoho_refresh_token
        if not token:
            raise ZohoConfigError(
                "No Zoho refresh token is available. Complete OAuth at /oauth/zoho/start first."
            )
        data = await self._token_request(
            {
                "grant_type": "refresh_token",
                "client_id": self.settings.zoho_client_id,
                "client_secret": self.settings.zoho_client_secret,
                "refresh_token": token,
            }
        )
        tokens = self._parse_token_response(
            data,
            previous=TokenSet(
                access_token="",
                refresh_token=token,
                expires_at=0,
                api_domain=self._tokens.api_domain if self._tokens else None,
            ),
        )
        self._tokens = tokens
        self.store.save(tokens)
        return tokens

    async def get_valid_access_token(self) -> str:
        tokens = self._tokens or self.store.load()
        self._tokens = tokens
        if tokens and tokens.access_token and not tokens.expired:
            return tokens.access_token
        refreshed = await self.refresh_access_token(tokens.refresh_token if tokens else None)
        return refreshed.access_token

    def current_tokens(self) -> TokenSet | None:
        return self._tokens or self.store.load()

    async def _token_request(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.settings.zoho_accounts_url}/oauth/v2/token"
        logger.info(
            "Requesting Zoho token grant_type=%s",
            params.get("grant_type"),
        )
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(url, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ZohoAuthError(
                f"Zoho token endpoint returned non-JSON (HTTP {response.status_code})."
            ) from exc
        if response.status_code >= 400 or payload.get("error"):
            error = payload.get("error") or payload.get("message") or response.text
            logger.warning(
                "Zoho token request failed status=%s payload=%s",
                response.status_code,
                redact_mapping(payload if isinstance(payload, dict) else {}),
            )
            raise ZohoAuthError(f"Zoho token request failed: {error}")
        return payload

    def _parse_token_response(self, data: dict[str, Any], previous: TokenSet | None) -> TokenSet:
        access_token = data.get("access_token")
        if not access_token:
            raise ZohoAuthError("Zoho token response did not include an access_token.")
        expires_in = int(data.get("expires_in") or 3600)
        refresh_token = data.get("refresh_token") or (previous.refresh_token if previous else None)
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=time.time() + expires_in,
            api_domain=data.get("api_domain") or (previous.api_domain if previous else None),
            token_type=data.get("token_type") or "Bearer",
        )
