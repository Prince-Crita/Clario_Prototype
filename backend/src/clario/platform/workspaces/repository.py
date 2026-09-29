"""All SQL for workspaces and memberships.

Membership lookups always filter on (workspace_id, user_id, active membership, live workspace);
this is the only path from a request to a WorkspaceScope.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import WorkspaceScope
from clario.platform.identity.models import User
from clario.platform.workspaces.models import MemberStatus, Workspace, WorkspaceMember


async def get_live_membership(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Workspace, WorkspaceMember] | None:
    row = (
        await session.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                Workspace.id == workspace_id,
                Workspace.deleted_at.is_(None),
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == MemberStatus.ACTIVE,
            )
        )
    ).one_or_none()
    return (row[0], row[1]) if row else None


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Workspace, WorkspaceMember]]:
    rows = await session.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MemberStatus.ACTIVE,
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.name)
    )
    return [(w, m) for w, m in rows.all()]


async def slug_for(session: AsyncSession, scope: WorkspaceScope) -> str:
    slug = await session.scalar(select(Workspace.slug).where(Workspace.id == scope.workspace_id))
    assert slug is not None  # the scope proves the workspace exists
    return slug


async def get_by_slug(session: AsyncSession, slug: str) -> Workspace | None:
    return await session.scalar(
        select(Workspace).where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
    )


async def get_member(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    return await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
    )


async def add_workspace(session: AsyncSession, workspace: Workspace) -> Workspace:
    session.add(workspace)
    await session.flush()
    return workspace


async def add_member(session: AsyncSession, member: WorkspaceMember) -> WorkspaceMember:
    session.add(member)
    await session.flush()
    return member


async def list_members(
    session: AsyncSession, scope: WorkspaceScope
) -> list[tuple[WorkspaceMember, User]]:
    rows = await session.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == scope.workspace_id,
            WorkspaceMember.status == MemberStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
        .order_by(User.full_name, User.email)
    )
    return [(m, u) for m, u in rows.all()]


async def list_all_for_operators(session: AsyncSession) -> list[tuple[str, str, str, int]]:
    """Cross-tenant listing for the `clario admin` CLI only — never exposed over HTTP."""
    active_members = func.count(WorkspaceMember.id).filter(
        WorkspaceMember.status == MemberStatus.ACTIVE
    )
    rows = await session.execute(
        select(Workspace.slug, Workspace.name, Workspace.status, active_members)
        .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(Workspace.deleted_at.is_(None))
        .group_by(Workspace.id)
        .order_by(Workspace.slug)
    )
    return [(slug, name, status, int(count)) for slug, name, status, count in rows.all()]


async def first_owner(session: AsyncSession, workspace_id: uuid.UUID) -> uuid.UUID | None:
    """For operator tooling that acts on a workspace's behalf (never exposed over HTTP)."""
    return await session.scalar(
        select(WorkspaceMember.user_id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MemberStatus.ACTIVE,
            WorkspaceMember.role == "owner",
        )
        .order_by(WorkspaceMember.created_at)
        .limit(1)
    )


async def name_for(session: AsyncSession, scope: WorkspaceScope) -> str:
    name = await session.scalar(select(Workspace.name).where(Workspace.id == scope.workspace_id))
    assert name is not None  # the scope proves the workspace exists
    return name
