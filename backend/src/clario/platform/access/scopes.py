"""Scope objects — the backbone of tenant isolation (plan §10.3, §13.3).

A `WorkspaceScope` can only be built by the access module after verifying an active membership
(`workspace_scope` dependency, or `load_workspace_scope` for flows without a workspace in the path
such as the OAuth callback). Repositories take a scope, never a bare workspace id from user input.

A `ConnectionScope` narrows it to one live integration connection of that workspace. It is built
only by `platform.connections` after checking the connection belongs to the scope's workspace.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from clario.platform.access.permissions import Permission, Role


@dataclass(frozen=True, slots=True)
class WorkspaceScope:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: Role
    permissions: frozenset[Permission]
    timezone: ZoneInfo
    base_currency: str
    fiscal_year_start_month: int

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


@dataclass(frozen=True, slots=True)
class ConnectionScope(WorkspaceScope):
    connection_id: uuid.UUID
    integration_key: str
    domain: str
