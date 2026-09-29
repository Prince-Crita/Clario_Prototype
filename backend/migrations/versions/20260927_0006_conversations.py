"""Assistant conversations (Phase 9; plan §14.2, §26).

* `core.conversations`: one user's conversation under one connection (composite FK, cascade;
  `UNIQUE (id, workspace_id)` for its messages).
* `core.messages`: user and assistant messages with provider, model, tokens, latency and the
  grounding flag.
* `core.tool_invocations`: every tool call of an assistant message (arguments, normalised result,
  status incl. `rejected`, duration).

Revision ID: 0006_conversations
Revises: 0005_finance
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_conversations"
down_revision: str | None = "0005_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_conversations_status")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_conversations_connection",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_conversations_id_workspace_id"),
        schema="core",
    )
    op.create_index(
        "ix_conversations_owner_recent",
        "conversations",
        ["workspace_id", "user_id", "connection_id", sa.literal_column("last_message_at DESC")],
        unique=False,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("grounding_flag", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_messages_role")),
        sa.CheckConstraint("status IN ('complete', 'failed')", name=op.f("ck_messages_status")),
        sa.ForeignKeyConstraint(
            ["conversation_id", "workspace_id"],
            ["core.conversations.id", "core.conversations.workspace_id"],
            name="fk_messages_conversation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        schema="core",
    )
    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
        schema="core",
    )
    op.create_table(
        "tool_invocations",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("round", sa.SmallInteger(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'no_data', 'error', 'rejected')",
            name=op.f("ck_tool_invocations_status"),
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["core.messages.id"],
            name=op.f("fk_tool_invocations_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_invocations")),
        schema="core",
    )
    op.create_index(
        "ix_tool_invocations_message_id",
        "tool_invocations",
        ["message_id"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_tool_invocations_message_id", table_name="tool_invocations", schema="core")
    op.drop_table("tool_invocations", schema="core")
    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages", schema="core")
    op.drop_table("messages", schema="core")
    op.drop_index(
        "ix_conversations_owner_recent",
        table_name="conversations",
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("conversations", schema="core")
