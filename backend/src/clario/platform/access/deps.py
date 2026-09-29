"""Workspace scope and permission dependencies (plan §10.3, §13.3).

`workspace_scope` is the ONLY way a route obtains a WorkspaceScope. A user who is not an active
member gets 404 — the same as a workspace that does not exist — so workspace ids cannot be probed.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.errors import NotFoundError, PermissionDeniedError
from clario.platform.access.permissions import Permission, Role, permissions_for
from clario.platform.access.scopes import WorkspaceScope
from clario.platform.identity.deps import AuthDep
from clario.platform.web import SessionDep
from clario.platform.workspaces import repository as workspace_repo
from clario.platform.workspaces.models import WorkspaceStatus

WORKSPACE_NOT_FOUND = "Workspace not found."


async def load_workspace_scope(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceScope:
    """Verify an active membership in an active workspace and build the scope (404 / 403)."""
    found = await workspace_repo.get_live_membership(session, workspace_id, user_id)
    if found is None:
        raise NotFoundError(WORKSPACE_NOT_FOUND, code="workspace.not_found")
    workspace, member = found
    if workspace.status != WorkspaceStatus.ACTIVE:
        raise PermissionDeniedError(
            "This workspace is not active. Contact Crita support.", code="workspace.inactive"
        )
    role = Role(member.role)
    return WorkspaceScope(
        workspace_id=workspace.id,
        user_id=user_id,
        role=role,
        permissions=permissions_for(role),
        timezone=ZoneInfo(workspace.timezone),
        base_currency=workspace.base_currency,
        fiscal_year_start_month=workspace.fiscal_year_start_month,
    )


async def workspace_scope(
    auth: AuthDep,
    session: SessionDep,
    workspace_id: Annotated[uuid.UUID, Path(description="Workspace id")],
) -> WorkspaceScope:
    return await load_workspace_scope(session, workspace_id, auth.user_id)


ScopeDep = Annotated[WorkspaceScope, Depends(workspace_scope)]


def require(permission: Permission) -> Callable[[WorkspaceScope], Awaitable[WorkspaceScope]]:
    """Dependency factory: `scope: Annotated[WorkspaceScope, Depends(require(Permission.X))]`."""

    async def checker(scope: ScopeDep) -> WorkspaceScope:
        if not scope.can(permission):
            raise PermissionDeniedError(code="auth.forbidden", extra={"required": permission.value})
        return scope

    checker.__name__ = f"require_{permission.value.replace('.', '_')}"
    return checker
