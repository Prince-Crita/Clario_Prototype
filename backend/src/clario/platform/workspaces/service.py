"""Workspace use cases: provisioning (used by the `clario admin` CLI) and member queries.

There is no public sign-up (plan §12, ADR-012): Crita provisions client workspaces and users.
Every provisioning action writes an audit row with actor_type `system` (CLI operator).
"""

from __future__ import annotations

import re
import uuid
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import utc_now
from clario.core.errors import ConflictError, NotFoundError, ValidationFailedError
from clario.platform.access.permissions import Role
from clario.platform.access.scopes import WorkspaceScope
from clario.platform.audit.service import ActorType, AuditAction, record
from clario.platform.identity import passwords
from clario.platform.identity import repository as identity_repo
from clario.platform.identity.models import User, UserStatus
from clario.platform.workspaces import repository as repo
from clario.platform.workspaces.models import (
    MemberStatus,
    Workspace,
    WorkspaceMember,
    WorkspaceStatus,
)

_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80].strip("-")
    if not slug:
        raise ValidationFailedError(
            "Workspace name must contain letters or digits.", code="workspace.invalid_name"
        )
    return slug


# ---------------------------------------------------------------- provisioning (CLI)
async def create_user(
    session: AsyncSession,
    *,
    email: str,
    full_name: str,
    password: str,
    is_platform_admin: bool = False,
) -> User:
    email = identity_repo.normalise_email(email)
    if len(email) > 320 or not _EMAIL.match(email):
        raise ValidationFailedError("Enter a valid email address.", code="user.invalid_email")
    if await identity_repo.get_user_by_email(session, email):
        raise ConflictError(f"A user with email {email} already exists.", code="user.exists")
    passwords.validate_password(password, email=email)
    user = await identity_repo.add_user(
        session,
        email=email,
        password_hash=passwords.hash_password(password),
        full_name=full_name,
        is_platform_admin=is_platform_admin,
    )
    record(
        session,
        AuditAction.USER_CREATED,
        actor_type=ActorType.SYSTEM,
        target_type="user",
        target_id=user.id,
        details={"email": email, "platform_admin": is_platform_admin},
    )
    return user


async def create_workspace(
    session: AsyncSession,
    *,
    name: str,
    owner_email: str,
    slug: str | None = None,
    timezone: str = "Asia/Kolkata",
    base_currency: str = "INR",
    fiscal_year_start_month: int = 4,
) -> Workspace:
    name = name.strip()
    if not name:
        raise ValidationFailedError("Workspace name is required.", code="workspace.invalid_name")
    slug = slug or slugify(name)
    if not _SLUG.match(slug):
        raise ValidationFailedError(
            "Slug may contain a-z, 0-9 and single hyphens.", code="workspace.invalid_slug"
        )
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationFailedError(
            f"Unknown time zone {timezone!r}.", code="workspace.invalid_timezone"
        ) from None
    if await repo.get_by_slug(session, slug):
        raise ConflictError(
            f"A workspace with slug {slug!r} already exists.", code="workspace.exists"
        )
    owner = await identity_repo.get_user_by_email(session, owner_email)
    if owner is None:
        raise NotFoundError(
            f"No user with email {owner_email}. Create the user first.", code="user.not_found"
        )

    workspace = await repo.add_workspace(
        session,
        Workspace(
            slug=slug,
            name=name,
            timezone=timezone,
            base_currency=base_currency.upper(),
            fiscal_year_start_month=fiscal_year_start_month,
            created_by=owner.id,
        ),
    )
    await repo.add_member(
        session, WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role=Role.OWNER)
    )
    record(
        session,
        AuditAction.WORKSPACE_CREATED,
        actor_type=ActorType.SYSTEM,
        workspace_id=workspace.id,
        target_type="workspace",
        target_id=workspace.id,
        details={"slug": slug, "owner": owner.email},
    )
    return workspace


async def _workspace_and_user(
    session: AsyncSession, slug: str, email: str
) -> tuple[Workspace, User]:
    workspace = await repo.get_by_slug(session, slug)
    if workspace is None:
        raise NotFoundError(f"No workspace with slug {slug!r}.", code="workspace.not_found")
    user = await identity_repo.get_user_by_email(session, email)
    if user is None:
        raise NotFoundError(f"No user with email {email}.", code="user.not_found")
    return workspace, user


async def set_member_role(
    session: AsyncSession, *, workspace_slug: str, email: str, role: Role
) -> WorkspaceMember:
    """Add the user with `role`, or change their role (re-activating a removed member)."""
    workspace, user = await _workspace_and_user(session, workspace_slug, email)
    member = await repo.get_member(session, workspace.id, user.id)
    details: dict[str, Any]
    if member is None:
        member = await repo.add_member(
            session, WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
        )
        action, details = AuditAction.MEMBER_ADDED, {"role": role.value}
    else:
        if member.role == Role.OWNER and role != Role.OWNER:
            await _ensure_another_owner(session, workspace.id, user.id)
        details = {
            "from": member.role,
            "to": role.value,
            "reactivated": member.status != MemberStatus.ACTIVE,
        }
        member.role, member.status = role, MemberStatus.ACTIVE
        action = AuditAction.MEMBER_ROLE_CHANGED
    record(
        session,
        action,
        actor_type=ActorType.SYSTEM,
        workspace_id=workspace.id,
        target_type="user",
        target_id=user.id,
        details={"email": user.email, **details},
    )
    return member


async def remove_member(session: AsyncSession, *, workspace_slug: str, email: str) -> None:
    workspace, user = await _workspace_and_user(session, workspace_slug, email)
    member = await repo.get_member(session, workspace.id, user.id)
    if member is None or member.status != MemberStatus.ACTIVE:
        raise NotFoundError(
            f"{email} is not a member of {workspace_slug}.", code="member.not_found"
        )
    if member.role == Role.OWNER:
        await _ensure_another_owner(session, workspace.id, user.id)
    member.status = MemberStatus.REMOVED
    record(
        session,
        AuditAction.MEMBER_REMOVED,
        actor_type=ActorType.SYSTEM,
        workspace_id=workspace.id,
        target_type="user",
        target_id=user.id,
        details={"email": user.email},
    )


async def _ensure_another_owner(
    session: AsyncSession, workspace_id: uuid.UUID, leaving_user: uuid.UUID
) -> None:
    owners = await session.scalar(
        select(func.count())
        .select_from(WorkspaceMember)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role == Role.OWNER,
            WorkspaceMember.status == MemberStatus.ACTIVE,
            WorkspaceMember.user_id != leaving_user,
        )
    )
    if not owners:
        raise ConflictError(
            "A workspace must keep at least one owner.", code="workspace.last_owner"
        )


async def set_workspace_status(
    session: AsyncSession, *, workspace_slug: str, status: WorkspaceStatus
) -> Workspace:
    workspace = await repo.get_by_slug(session, workspace_slug)
    if workspace is None:
        raise NotFoundError(
            f"No workspace with slug {workspace_slug!r}.", code="workspace.not_found"
        )
    previous, workspace.status = workspace.status, status
    record(
        session,
        AuditAction.WORKSPACE_STATUS_CHANGED,
        actor_type=ActorType.SYSTEM,
        workspace_id=workspace.id,
        target_type="workspace",
        target_id=workspace.id,
        details={"from": previous, "to": status.value},
    )
    return workspace


async def set_user_status(session: AsyncSession, *, email: str, status: UserStatus) -> User:
    user = await identity_repo.get_user_by_email(session, email)
    if user is None:
        raise NotFoundError(f"No user with email {email}.", code="user.not_found")
    user.status = status
    if status == UserStatus.DISABLED:
        await identity_repo.revoke_user_sessions(session, user.id, utc_now())
    record(
        session,
        AuditAction.USER_DISABLED if status == UserStatus.DISABLED else AuditAction.USER_ENABLED,
        actor_type=ActorType.SYSTEM,
        target_type="user",
        target_id=user.id,
        details={"email": user.email},
    )
    return user


async def reset_password(session: AsyncSession, *, email: str, new_password: str) -> User:
    """Operator reset: sets a new password, clears lockout, signs the user out everywhere."""
    user = await identity_repo.get_user_by_email(session, email)
    if user is None:
        raise NotFoundError(f"No user with email {email}.", code="user.not_found")
    passwords.validate_password(new_password, email=user.email)
    user.password_hash = passwords.hash_password(new_password)
    user.failed_login_count, user.locked_until = 0, None
    revoked = await identity_repo.revoke_user_sessions(session, user.id, utc_now())
    record(
        session,
        AuditAction.PASSWORD_RESET,
        actor_type=ActorType.SYSTEM,
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "sessions_revoked": revoked},
    )
    return user


# ---------------------------------------------------------------- queries (API)
async def list_members(
    session: AsyncSession, scope: WorkspaceScope
) -> list[tuple[WorkspaceMember, User]]:
    return await repo.list_members(session, scope)
