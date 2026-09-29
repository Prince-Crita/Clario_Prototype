"""The credential vault: the only code that encrypts or decrypts connection secrets (plan §29).

Connectors call it through their token manager:
  * `load` — decrypt the secret (optionally `SELECT … FOR UPDATE`, to serialise token refresh
    across workers);
  * `store` — encrypt with the active key and upsert (re-encrypting rows left on an old key);
  * `mark_needs_reauth` — the provider rejected the credentials: flag the connection and COMMIT,
    so the flag survives the error the caller is about to raise.
Secrets are JSON objects defined by each connector; core never interprets them.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.crypto import DecryptionError, Encryptor
from clario.core.dates import utc_now
from clario.core.errors import ConflictError, ServiceUnavailableError
from clario.platform.access.scopes import ConnectionScope
from clario.platform.audit.service import ActorType, AuditAction, record
from clario.platform.connections import repository as repo
from clario.platform.connections.models import ConnectionStatus
from clario.settings import Settings

logger = logging.getLogger(__name__)

NEEDS_REAUTH_CODE = "connection.needs_reauth"


def encryptor(settings: Settings) -> Encryptor:
    return Encryptor(settings.fernet_keys)


def needs_reauth_error(name: str) -> ConflictError:
    return ConflictError(
        f"{name} stopped accepting Clario's access. "
        "A workspace owner or admin needs to reconnect it.",
        code=NEEDS_REAUTH_CODE,
    )


async def load(
    session: AsyncSession, settings: Settings, scope: ConnectionScope, *, for_update: bool = False
) -> dict[str, Any]:
    row = await repo.get_credential(session, scope, for_update=for_update)
    if row is None:
        raise ConflictError(
            "This connection has not been authorised yet.", code="connection.not_authorised"
        )
    try:
        secret: dict[str, Any] = json.loads(encryptor(settings).decrypt(row.ciphertext))
    except DecryptionError:
        logger.error(
            "Connection credentials cannot be decrypted with the configured keys",
            extra={"connection_id": str(scope.connection_id), "key_id": row.key_id},
        )
        raise ServiceUnavailableError(
            "Clario cannot read this connection's credentials. Contact Crita support.",
            code="connection.credentials_unreadable",
        ) from None
    return secret


async def load_optional(
    session: AsyncSession, settings: Settings, scope: ConnectionScope
) -> dict[str, Any] | None:
    try:
        return await load(session, settings, scope)
    except (ConflictError, ServiceUnavailableError):
        return None


async def store(
    session: AsyncSession,
    settings: Settings,
    scope: ConnectionScope,
    secret: Mapping[str, Any],
    *,
    granted_scopes: Sequence[str] | None = None,
) -> None:
    """Encrypt and save. `granted_scopes=None` keeps the scopes already recorded."""
    sealed = encryptor(settings).encrypt(json.dumps(dict(secret), separators=(",", ":")).encode())
    await repo.put_credential(
        session,
        scope,
        ciphertext=sealed.ciphertext,
        key_id=sealed.key_id,
        granted_scopes=granted_scopes,
    )


async def mark_needs_reauth(session: AsyncSession, scope: ConnectionScope, code: str) -> None:
    connection = await repo.get_live(session, scope, scope.connection_id)
    if connection is None:
        return
    now = utc_now()
    connection.status = ConnectionStatus.NEEDS_REAUTH
    connection.last_error_code = code
    connection.last_error_at = now
    record(
        session,
        AuditAction.CONNECTION_NEEDS_REAUTH,
        actor_type=ActorType.SYSTEM,
        workspace_id=scope.workspace_id,
        target_type="connection",
        target_id=scope.connection_id,
        details={"integration": scope.integration_key, "reason": code},
    )
    await session.commit()
