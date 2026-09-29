"""Append-only audit trail (plan §14.2, §29).

No foreign keys on purpose: audit history must survive deletion of users and workspaces.
The application only ever INSERTs; production grants should deny UPDATE/DELETE on this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base

SCHEMA = "core"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_workspace_occurred", "workspace_id", text("occurred_at DESC")),
        Index("ix_audit_logs_actor_occurred", "actor_user_id", text("occurred_at DESC")),
        CheckConstraint("actor_type IN ('user', 'platform_admin', 'system')", name="actor_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    workspace_id: Mapped[uuid.UUID | None]
    actor_user_id: Mapped[uuid.UUID | None]
    actor_type: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
