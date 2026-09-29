"""Token manager (plan §16.4): a valid access token for a connection, refreshing when needed.

Refresh is serialised per connection with `SELECT … FOR UPDATE` on the credentials row, so two
workers never spend the same refresh token twice; the second waits, then finds a fresh token.
A refresh token Zoho rejects moves the connection to `needs_reauth` (committed) and raises 409
`connection.needs_reauth`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from clario.core.dates import utc_now
from clario.integrations.zoho_books import oauth
from clario.integrations.zoho_books.manifest import MANIFEST
from clario.platform.connections import vault
from clario.platform.integrations.contract import ConnectionContext

logger = logging.getLogger(__name__)

REFRESH_MARGIN = timedelta(minutes=2)
REAUTH_CODE = "zoho.refresh_rejected"


@dataclass(frozen=True, slots=True)
class ZohoSecret:
    refresh_token: str
    access_token: str
    access_expires_at: datetime
    accounts_server: str
    api_domain: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ZohoSecret:
        return cls(
            refresh_token=str(data["refresh_token"]),
            access_token=str(data["access_token"]),
            access_expires_at=datetime.fromisoformat(str(data["access_expires_at"])),
            accounts_server=str(data["accounts_server"]),
            api_domain=str(data["api_domain"]),
        )

    def to_json(self) -> dict[str, str]:
        return {
            "refresh_token": self.refresh_token,
            "access_token": self.access_token,
            "access_expires_at": self.access_expires_at.isoformat(),
            "accounts_server": self.accounts_server,
            "api_domain": self.api_domain,
        }

    def is_fresh(self, now: datetime) -> bool:
        return self.access_expires_at - REFRESH_MARGIN > now


async def valid_secret(context: ConnectionContext) -> ZohoSecret:
    session, settings, scope = context.session, context.settings, context.scope
    secret = ZohoSecret.from_json(await vault.load(session, settings, scope))
    if secret.is_fresh(utc_now()):
        return secret

    # Lock, then re-read: another worker may have refreshed while we waited.
    secret = ZohoSecret.from_json(await vault.load(session, settings, scope, for_update=True))
    now = utc_now()
    if secret.is_fresh(now):
        return secret
    try:
        token = await oauth.refresh(settings, secret.accounts_server, secret.refresh_token)
    except oauth.ZohoTokenRejectedError as exc:
        logger.warning(
            "Zoho rejected the refresh token; connection needs reauthorisation",
            extra={"connection_id": str(scope.connection_id), "zoho_error": exc.error},
        )
        await vault.mark_needs_reauth(session, scope, REAUTH_CODE)
        raise vault.needs_reauth_error(MANIFEST.name) from None
    secret = replace(
        secret,
        access_token=token.access_token,
        access_expires_at=now + timedelta(seconds=token.expires_in),
    )
    await vault.store(session, settings, scope, secret.to_json())
    return secret
