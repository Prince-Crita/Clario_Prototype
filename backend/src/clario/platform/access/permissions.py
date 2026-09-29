"""Roles and permissions (plan §13.2).

Roles are fixed and mapped to permissions in code: small, explicit, exhaustively tested. A roles
table is only worth it once custom roles are a product requirement.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Permission(StrEnum):
    WORKSPACE_VIEW = "workspace.view"
    FINANCE_VIEW = "finance.view"
    ASSISTANT_USE = "assistant.use"
    INTEGRATIONS_MANAGE = "integrations.manage"
    MEMBERS_MANAGE = "members.manage"


_VIEWER = frozenset({Permission.WORKSPACE_VIEW, Permission.FINANCE_VIEW})
_MEMBER = _VIEWER | {Permission.ASSISTANT_USE}
_ADMIN = _MEMBER | {Permission.INTEGRATIONS_MANAGE}
_OWNER = _ADMIN | {Permission.MEMBERS_MANAGE}

ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.OWNER: _OWNER,
    Role.ADMIN: _ADMIN,
    Role.MEMBER: _MEMBER,
    Role.VIEWER: _VIEWER,
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[Role(role)]
