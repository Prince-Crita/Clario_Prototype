"""Workspace API contracts."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from clario.platform.access.permissions import Permission, Role


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: str
    role: Role


class WorkspaceDetail(WorkspaceSummary):
    timezone: str
    base_currency: str
    fiscal_year_start_month: int
    permissions: list[Permission]


class Member(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: Role


class WorkspaceList(BaseModel):
    workspaces: list[WorkspaceSummary]


class MemberList(BaseModel):
    members: list[Member]
