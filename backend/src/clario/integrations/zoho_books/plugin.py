"""Zoho Books connector entry point (the object registered in `clario.api.registry`).

Provider specifics only; core runs the flow (plan §15.1, §17): the consent URL, exchanging the code
(with the data-center allow-list and a scope check), organisations, and revocation.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from clario.core.dates import utc_now
from clario.core.errors import UpstreamError, ValidationFailedError
from clario.integrations.zoho_books import oauth, organizations
from clario.integrations.zoho_books.manifest import MANIFEST
from clario.integrations.zoho_books.regions import (
    DATA_CENTERS,
    allowed_api_domain,
    by_accounts_server,
)
from clario.integrations.zoho_books.source import ZohoFinanceSource
from clario.integrations.zoho_books.tokens import ZohoSecret
from clario.platform.integrations.contract import (
    AccountProfile,
    ConnectFailedError,
    ConnectFailure,
    ConnectionContext,
    ConsentRedirect,
    ExternalAccount,
    Grant,
    IntegrationManifest,
)
from clario.settings import Settings

logger = logging.getLogger(__name__)


class ZohoBooksPlugin:
    @property
    def manifest(self) -> IntegrationManifest:
        return MANIFEST

    def consent_redirect(
        self, settings: Settings, *, state: str, region: str | None
    ) -> ConsentRedirect:
        oauth.require_configured(settings)
        dc = DATA_CENTERS.get(region or settings.zoho_default_region)
        if dc is None:
            raise ValidationFailedError(
                "Choose where your Zoho account is hosted.", code="integration.invalid_region"
            )
        return ConsentRedirect(
            url=oauth.authorize_url(settings, dc.accounts_server, state), region=dc.code
        )

    async def exchange(
        self, settings: Settings, callback: Mapping[str, str], *, region: str | None
    ) -> Grant:
        code = callback.get("code", "")
        if not code:
            raise ConnectFailedError(ConnectFailure.EXCHANGE_FAILED, "no code on the redirect")
        fallback = DATA_CENTERS.get(region or settings.zoho_default_region)
        server = callback.get("accounts-server") or (fallback.accounts_server if fallback else "")
        dc = by_accounts_server(server)
        if dc is None:
            raise ConnectFailedError(ConnectFailure.SERVER_REJECTED, f"accounts-server {server!r}")
        try:
            token = await oauth.exchange_code(settings, dc.accounts_server, code)
        except oauth.ZohoTokenRejectedError as exc:
            raise ConnectFailedError(ConnectFailure.EXCHANGE_FAILED, exc.error) from None
        except UpstreamError as exc:
            raise ConnectFailedError(ConnectFailure.PROVIDER_ERROR, exc.code) from None
        if not token.refresh_token:
            raise ConnectFailedError(ConnectFailure.EXCHANGE_FAILED, "no refresh token issued")

        api_domain = allowed_api_domain(token.api_domain or dc.api_domain)
        missing = _missing_scopes(settings.zoho_scope_list, token.scopes)
        if api_domain is None or missing:
            await _revoke_quietly(dc.accounts_server, token.refresh_token)
            if api_domain is None:
                raise ConnectFailedError(
                    ConnectFailure.SERVER_REJECTED, f"api_domain {token.api_domain!r}"
                )
            raise ConnectFailedError(ConnectFailure.MISSING_SCOPES, ",".join(missing))

        secret = ZohoSecret(
            refresh_token=token.refresh_token,
            access_token=token.access_token,
            access_expires_at=utc_now() + timedelta(seconds=token.expires_in),
            accounts_server=dc.accounts_server,
            api_domain=api_domain,
        )
        return Grant(secret=secret.to_json(), granted_scopes=token.scopes, region=dc.code)

    async def list_accounts(self, context: ConnectionContext) -> list[ExternalAccount]:
        return await organizations.list_organizations(context)

    async def account_profile(self, context: ConnectionContext, account_id: str) -> AccountProfile:
        return await organizations.organization_profile(context, account_id)

    async def revoke(self, settings: Settings, secret: Mapping[str, Any]) -> None:
        stored = ZohoSecret.from_json(dict(secret))
        dc = by_accounts_server(stored.accounts_server)
        if dc is not None:  # never send a token to a server outside the allow-list
            await oauth.revoke(dc.accounts_server, stored.refresh_token)

    def data_source(self, context: ConnectionContext) -> ZohoFinanceSource:
        return ZohoFinanceSource(context)


def _missing_scopes(required: list[str], granted: tuple[str, ...]) -> list[str]:
    """Required scopes Zoho did not grant. An absent scope list cannot be checked: allowed."""
    if not granted:
        return []
    have = {s.lower() for s in granted}
    return [s for s in required if s.lower() not in have]


async def _revoke_quietly(accounts_server: str, refresh_token: str) -> None:
    try:
        await oauth.revoke(accounts_server, refresh_token)
    except Exception:
        logger.warning("Could not revoke an unusable Zoho grant")


plugin = ZohoBooksPlugin()
