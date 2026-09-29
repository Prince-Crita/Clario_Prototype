"""Read models: connections as the API shows them (used by the connection and catalog routes)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import WorkspaceScope
from clario.platform.connections.models import Connection, ConnectionCredential
from clario.platform.connections.schemas import ConnectionAccount, ConnectionOut
from clario.platform.identity.models import User


async def describe(
    session: AsyncSession, scope: WorkspaceScope, connections: Iterable[Connection]
) -> dict[uuid.UUID, ConnectionOut]:
    connections = [c for c in connections if c.workspace_id == scope.workspace_id]
    ids = [c.id for c in connections]
    authorised = set(
        await session.scalars(
            select(ConnectionCredential.connection_id).where(
                ConnectionCredential.workspace_id == scope.workspace_id,
                ConnectionCredential.connection_id.in_(ids),
            )
        )
    )
    user_ids = {c.connected_by for c in connections if c.connected_by}
    names = {
        row.id: row.full_name or row.email
        for row in await session.execute(
            select(User.id, User.full_name, User.email).where(User.id.in_(user_ids))
        )
    }
    return {c.id: _out(c, c.id in authorised, names.get(c.connected_by)) for c in connections}


def _out(connection: Connection, authorised: bool, connected_by: str | None) -> ConnectionOut:
    settings = connection.settings or {}
    account = (
        ConnectionAccount(
            id=connection.external_account_id,
            name=connection.external_account_name or connection.external_account_id,
            currency=settings.get("currency"),
            timezone=settings.get("timezone"),
            fiscal_year_start_month=settings.get("fiscal_year_start_month"),
        )
        if connection.external_account_id
        else None
    )
    return ConnectionOut(
        id=connection.id,
        integration_key=connection.integration_key,
        status=connection.status,  # live rows are never 'disconnected'
        authorised=authorised,
        account=account,
        region=connection.region,
        connected_at=connection.connected_at,
        connected_by=connected_by,
        last_verified_at=connection.last_verified_at,
        last_error_code=connection.last_error_code,
    )
