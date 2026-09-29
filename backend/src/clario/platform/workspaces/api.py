"""Workspace routes (plan §11.2). Every workspace-scoped route depends on `workspace_scope`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from clario.platform.access.deps import require
from clario.platform.access.permissions import Permission, Role
from clario.platform.access.scopes import WorkspaceScope
from clario.platform.identity.deps import AuthDep
from clario.platform.web import SessionDep
from clario.platform.workspaces import repository, service
from clario.platform.workspaces.schemas import (
    Member,
    MemberList,
    WorkspaceDetail,
    WorkspaceList,
    WorkspaceSummary,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
CanView = Annotated[WorkspaceScope, Depends(require(Permission.WORKSPACE_VIEW))]


@router.get("", response_model=WorkspaceList, summary="Workspaces I belong to")
async def list_my_workspaces(auth: AuthDep, session: SessionDep) -> WorkspaceList:
    rows = await repository.list_for_user(session, auth.user_id)
    return WorkspaceList(
        workspaces=[
            WorkspaceSummary(id=w.id, slug=w.slug, name=w.name, status=w.status, role=Role(m.role))
            for w, m in rows
        ]
    )


@router.get("/{workspace_id}", response_model=WorkspaceDetail, summary="One workspace")
async def get_workspace(scope: CanView, session: SessionDep) -> WorkspaceDetail:
    found = await repository.get_live_membership(session, scope.workspace_id, scope.user_id)
    assert found is not None  # guaranteed by workspace_scope
    workspace, _ = found
    return WorkspaceDetail(
        id=workspace.id,
        slug=workspace.slug,
        name=workspace.name,
        status=workspace.status,
        role=scope.role,
        timezone=workspace.timezone,
        base_currency=workspace.base_currency,
        fiscal_year_start_month=workspace.fiscal_year_start_month,
        permissions=sorted(scope.permissions),
    )


@router.get("/{workspace_id}/members", response_model=MemberList, summary="Workspace members")
async def list_members(scope: CanView, session: SessionDep) -> MemberList:
    rows = await service.list_members(session, scope)
    return MemberList(
        members=[
            Member(user_id=u.id, email=u.email, full_name=u.full_name, role=Role(m.role))
            for m, u in rows
        ]
    )
