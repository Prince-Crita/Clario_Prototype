"""Workspace (tenant) tables in the `core` schema (plan §13, §14.2)."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, SoftDelete, Timestamps, UUIDPrimaryKey
from clario.platform.access.permissions import Role

SCHEMA = "core"
_ROLES = ", ".join(f"'{r.value}'" for r in Role)


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class MemberStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class Workspace(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        Index(
            "uq_workspaces_slug_live",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("status IN ('active', 'suspended', 'archived')", name="status"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        CheckConstraint("fiscal_year_start_month BETWEEN 1 AND 12", name="fiscal_year_start_month"),
        CheckConstraint("base_currency ~ '^[A-Z]{3}$'", name="base_currency"),
        {"schema": SCHEMA},
    )

    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(16), default=WorkspaceStatus.ACTIVE, server_default="active"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Kolkata", server_default="Asia/Kolkata"
    )
    base_currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    fiscal_year_start_month: Mapped[int] = mapped_column(
        SmallInteger, default=4, server_default="4"
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.users.id", ondelete="SET NULL")
    )


class WorkspaceMember(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        Index("ix_workspace_members_user_id", "user_id"),
        CheckConstraint(f"role IN ({_ROLES})", name="role"),
        CheckConstraint("status IN ('active', 'removed')", name="status"),
        {"schema": SCHEMA},
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.workspaces.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(
        String(16), default=MemberStatus.ACTIVE, server_default="active"
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.users.id", ondelete="SET NULL")
    )
