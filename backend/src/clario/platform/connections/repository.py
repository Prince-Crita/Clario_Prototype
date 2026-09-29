"""All SQL for connections, their credentials and OAuth states. Every read is scoped."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy import ColumnElement, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.ids import uuid7
from clario.platform.access.scopes import ConnectionScope, WorkspaceScope
from clario.platform.connections.models import (
    Connection,
    ConnectionCredential,
    ConnectionStatus,
    OAuthState,
)


def _live(scope: WorkspaceScope) -> list[ColumnElement[bool]]:
    return [Connection.workspace_id == scope.workspace_id, Connection.deleted_at.is_(None)]


async def live_connections(session: AsyncSession, scope: WorkspaceScope) -> dict[str, Connection]:
    """The workspace's live connection per integration key (at most one each)."""
    rows = await session.scalars(select(Connection).where(*_live(scope)))
    return {c.integration_key: c for c in rows}


async def live_connection_for(
    session: AsyncSession, scope: WorkspaceScope, integration_key: str
) -> Connection | None:
    return await session.scalar(
        select(Connection).where(*_live(scope), Connection.integration_key == integration_key)
    )


async def get_live(
    session: AsyncSession, scope: WorkspaceScope, connection_id: uuid.UUID
) -> Connection | None:
    return await session.scalar(
        select(Connection).where(*_live(scope), Connection.id == connection_id)
    )


async def ensure_pending(
    session: AsyncSession, scope: WorkspaceScope, integration_key: str, region: str | None
) -> Connection:
    """The live connection for this integration, creating a pending one if there is none.

    Safe under concurrency: the partial unique index decides, and the loser reads the winner's row.
    """
    await session.execute(
        insert(Connection)
        .values(
            id=uuid7(),
            workspace_id=scope.workspace_id,
            integration_key=integration_key,
            status=ConnectionStatus.PENDING.value,
            region=region,
            settings={},
        )
        .on_conflict_do_nothing(
            index_elements=[Connection.workspace_id, Connection.integration_key],
            index_where=Connection.deleted_at.is_(None),
        )
    )
    connection = await live_connection_for(session, scope, integration_key)
    assert connection is not None
    return connection


# ---------------------------------------------------------------- credentials


async def get_credential(
    session: AsyncSession, scope: ConnectionScope, *, for_update: bool = False
) -> ConnectionCredential | None:
    # populate_existing: the row may have been rewritten by put_credential (a Core upsert) earlier
    # in this session, so never trust the identity map's copy.
    statement = (
        select(ConnectionCredential)
        .where(
            ConnectionCredential.connection_id == scope.connection_id,
            ConnectionCredential.workspace_id == scope.workspace_id,
        )
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


async def put_credential(
    session: AsyncSession,
    scope: ConnectionScope,
    *,
    ciphertext: bytes,
    key_id: str,
    granted_scopes: Sequence[str] | None,
) -> None:
    values: dict[str, object] = {"ciphertext": ciphertext, "key_id": key_id}
    if granted_scopes is not None:
        values["granted_scopes"] = list(granted_scopes)
    statement = insert(ConnectionCredential).values(
        connection_id=scope.connection_id, workspace_id=scope.workspace_id, **values
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[ConnectionCredential.connection_id],
            set_={**{k: statement.excluded[k] for k in values}, "updated_at": func.now()},
        )
    )


async def delete_credential(session: AsyncSession, scope: ConnectionScope) -> None:
    await session.execute(
        delete(ConnectionCredential).where(
            ConnectionCredential.connection_id == scope.connection_id,
            ConnectionCredential.workspace_id == scope.workspace_id,
        )
    )


async def has_credential(session: AsyncSession, scope: ConnectionScope) -> bool:
    return (await get_credential(session, scope)) is not None


# ---------------------------------------------------------------- OAuth states


def add_state(session: AsyncSession, state: OAuthState) -> None:
    session.add(state)


async def consume_state(
    session: AsyncSession, state_hash: bytes, integration_key: str, now: datetime
) -> OAuthState | None:
    """Atomically mark a state used. Returns it only if it existed, was unused and unexpired."""
    row = await session.execute(
        update(OAuthState)
        .where(
            OAuthState.state_hash == state_hash,
            OAuthState.integration_key == integration_key,
            OAuthState.consumed_at.is_(None),
            OAuthState.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(OAuthState)
    )
    return row.scalar_one_or_none()


async def find_state(
    session: AsyncSession, state_hash: bytes, integration_key: str
) -> OAuthState | None:
    return await session.scalar(
        select(OAuthState).where(
            OAuthState.state_hash == state_hash, OAuthState.integration_key == integration_key
        )
    )


async def delete_states_for(session: AsyncSession, scope: ConnectionScope) -> None:
    await session.execute(
        delete(OAuthState).where(
            OAuthState.connection_id == scope.connection_id,
            OAuthState.workspace_id == scope.workspace_id,
        )
    )


async def purge_states_before(session: AsyncSession, cutoff: datetime) -> None:
    await session.execute(delete(OAuthState).where(OAuthState.expires_at < cutoff))


LockMode = Literal["update", "no_key_update", "key_share"]


async def lock_live(
    session: AsyncSession, scope: ConnectionScope, mode: LockMode = "update"
) -> Connection | None:
    """The live connection, row-locked for this transaction. PostgreSQL row-lock levels:

    * `update` (FOR UPDATE) — disconnect: waits for any dataset being written;
    * `no_key_update` (FOR NO KEY UPDATE) — starting a sync: serialises triggers without
      waiting for a dataset write;
    * `key_share` (FOR KEY SHARE) — writing a dataset: blocks a disconnect (so nothing lands after
      a purge) but not ordinary updates such as marking the connection `needs_reauth`.
    """
    statement = select(Connection).where(*_live(scope), Connection.id == scope.connection_id)
    if mode == "update":
        statement = statement.with_for_update()
    elif mode == "no_key_update":
        statement = statement.with_for_update(key_share=True)
    else:
        statement = statement.with_for_update(read=True, key_share=True)
    return await session.scalar(statement.execution_options(populate_existing=True))
