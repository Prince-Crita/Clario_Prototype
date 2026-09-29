"""Audit writer. Call inside the caller's transaction so the audit row commits with the change.

`details` is passed through the log redactor, so a careless caller cannot persist a token.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.logs import redact
from clario.platform.audit.models import AuditLog
from clario.platform.web import ClientInfo


class ActorType(StrEnum):
    USER = "user"
    PLATFORM_ADMIN = "platform_admin"
    SYSTEM = "system"


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login.succeeded"
    LOGIN_FAILED = "auth.login.failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password.changed"  # noqa: S105 - event name, not a secret
    PASSWORD_RESET = "auth.password.reset"  # noqa: S105 - event name, not a secret
    SESSIONS_REVOKED = "auth.sessions.revoked"
    USER_CREATED = "user.created"
    USER_DISABLED = "user.disabled"
    USER_ENABLED = "user.enabled"
    WORKSPACE_CREATED = "workspace.created"
    WORKSPACE_STATUS_CHANGED = "workspace.status_changed"
    MEMBER_ADDED = "member.added"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    INTEGRATION_CONNECT_STARTED = "integration.connect_started"
    INTEGRATION_CONNECT_FAILED = "integration.connect_failed"
    INTEGRATION_AUTHORIZED = "integration.authorized"
    INTEGRATION_CONNECTED = "integration.connected"
    INTEGRATION_RECONNECTED = "integration.reconnected"
    INTEGRATION_DISCONNECTED = "integration.disconnected"
    INTEGRATION_VISIBILITY_CHANGED = "integration.visibility_changed"
    CONNECTION_NEEDS_REAUTH = "connection.needs_reauth"
    CONVERSATION_DELETED = "conversation.deleted"


def record(
    session: AsyncSession,
    action: AuditAction,
    *,
    actor_type: ActorType = ActorType.USER,
    actor_user_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    client: ClientInfo | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            action=action.value,
            actor_type=actor_type.value,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip=client.ip if client else None,
            user_agent=client.user_agent if client else None,
            details=redact(details or {}),
        )
    )
