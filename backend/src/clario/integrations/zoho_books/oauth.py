"""Zoho Accounts OAuth for Crita's server-based application (plan §17).

Secrets travel in the POST body, never in a URL. Zoho reports most failures as HTTP 200 with an
`error` field, so both the status and the body are checked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from clario.core.errors import ServiceUnavailableError, UpstreamError
from clario.settings import Settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(20.0)


class ZohoTokenRejectedError(Exception):
    """Zoho refused the code or refresh token (revoked, expired, already used)."""

    def __init__(self, error: str) -> None:
        self.error = error
        super().__init__(error)


@dataclass(frozen=True, slots=True)
class TokenResponse:
    access_token: str
    refresh_token: str | None
    api_domain: str | None
    expires_in: int
    scopes: tuple[str, ...]


def require_configured(settings: Settings) -> None:
    if not (
        settings.zoho_client_id
        and settings.zoho_client_secret.get_secret_value()
        and settings.zoho_scope_list
    ):
        raise ServiceUnavailableError(
            "Zoho Books is not configured on this server. Contact Crita support.",
            code="integration.not_configured",
        )


def authorize_url(settings: Settings, accounts_server: str, state: str) -> str:
    query = urlencode(
        {
            "scope": ",".join(settings.zoho_scope_list),
            "client_id": settings.zoho_client_id,
            "response_type": "code",
            "redirect_uri": settings.zoho_redirect_uri,
            "access_type": "offline",  # a refresh token, so Clario can read without the user
            "prompt": "consent",  # always issue a fresh refresh token (reconnect)
            "state": state,
        }
    )
    return f"{accounts_server}/oauth/v2/auth?{query}"


async def _token_request(accounts_server: str, form: dict[str, str]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as http:
            response = await http.post(f"{accounts_server}/oauth/v2/token", data=form)
    except httpx.HTTPError as exc:
        logger.warning("Zoho Accounts unreachable", extra={"error": type(exc).__name__})
        raise UpstreamError(
            "Zoho could not be reached. Try again.", code="zoho.unavailable"
        ) from None
    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 500:
        raise UpstreamError("Zoho is having problems. Try again.", code="zoho.unavailable")
    if response.status_code >= 400 or "error" in payload or "access_token" not in payload:
        raise ZohoTokenRejectedError(str(payload.get("error") or f"http_{response.status_code}"))
    return payload


def _parse(payload: dict[str, Any]) -> TokenResponse:
    scope = str(payload.get("scope") or "")
    return TokenResponse(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
        api_domain=str(payload["api_domain"]) if payload.get("api_domain") else None,
        expires_in=int(payload.get("expires_in") or 3600),
        scopes=tuple(s for s in scope.replace(" ", ",").split(",") if s),
    )


async def exchange_code(settings: Settings, accounts_server: str, code: str) -> TokenResponse:
    return _parse(
        await _token_request(
            accounts_server,
            {
                "grant_type": "authorization_code",
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret.get_secret_value(),
                "redirect_uri": settings.zoho_redirect_uri,
                "code": code,
            },
        )
    )


async def refresh(settings: Settings, accounts_server: str, refresh_token: str) -> TokenResponse:
    return _parse(
        await _token_request(
            accounts_server,
            {
                "grant_type": "refresh_token",
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret.get_secret_value(),
                "refresh_token": refresh_token,
            },
        )
    )


async def revoke(accounts_server: str, refresh_token: str) -> None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        response = await http.post(
            f"{accounts_server}/oauth/v2/token/revoke", data={"token": refresh_token}
        )
    response.raise_for_status()
