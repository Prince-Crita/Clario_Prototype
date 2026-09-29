"""`ConnectionScope` dependency: a live connection of the caller's workspace, or 404."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Path

from clario.platform.access.deps import require
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import ConnectionScope, WorkspaceScope
from clario.platform.connections import service
from clario.platform.integrations.deps import RegistryDep
from clario.platform.web import SessionDep


def connection_access(
    permission: Permission,
) -> Callable[..., Awaitable[ConnectionScope]]:
    """Dependency factory: the workspace check, then `permission`, then the connection lookup.

    `scope` uses a default-value `Depends` because postponed annotations cannot see `permission`.
    """
    checked_scope = Depends(require(permission))

    async def dependency(
        connection_id: Annotated[uuid.UUID, Path(description="Connection id")],
        session: SessionDep,
        registry: RegistryDep,
        scope: WorkspaceScope = checked_scope,
    ) -> ConnectionScope:
        return await service.connection_scope(session, registry, scope, connection_id)

    dependency.__name__ = f"connection_{permission.value.replace('.', '_')}"
    return dependency


ViewConnection = Annotated[ConnectionScope, Depends(connection_access(Permission.WORKSPACE_VIEW))]
ManageConnection = Annotated[
    ConnectionScope, Depends(connection_access(Permission.INTEGRATIONS_MANAGE))
]
