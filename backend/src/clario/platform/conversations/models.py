"""Conversation tables in `core` (plan §14.2, §26): every message and tool invocation is stored, so
history survives restarts and works across workers. A conversation belongs to one user and one
connection; composite FKs keep its messages in its workspace."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, SoftDelete, Timestamps, UUIDPrimaryKey

SCHEMA = "core"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    COMPLETE = "complete"
    FAILED = "failed"


class Conversation(UUIDPrimaryKey, Timestamps, SoftDelete, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_conversations_connection",
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_conversations_id_workspace_id"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        Index(
            "ix_conversations_owner_recent",
            "workspace_id",
            "user_id",
            "connection_id",
            text("last_message_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": SCHEMA},
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column()
    connection_id: Mapped[uuid.UUID] = mapped_column()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(UUIDPrimaryKey, Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "workspace_id"],
            ["core.conversations.id", "core.conversations.workspace_id"],
            name="fk_messages_conversation",
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint("status IN ('complete', 'failed')", name="status"),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
        {"schema": SCHEMA},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column()
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default=MessageStatus.COMPLETE)
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    grounding_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()")
    )


class ToolInvocation(UUIDPrimaryKey, Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'no_data', 'error', 'rejected')", name="status"),
        Index("ix_tool_invocations_message_id", "message_id"),
        {"schema": SCHEMA},
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.messages.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    call_id: Mapped[str] = mapped_column(String(64))
    round: Mapped[int] = mapped_column(SmallInteger)
    tool_name: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()")
    )
