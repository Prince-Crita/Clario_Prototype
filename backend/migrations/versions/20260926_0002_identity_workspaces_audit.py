"""Identity, workspaces and audit (Phase 2; plan §12–§14.2).

Tables in `core`: users, user_sessions, workspaces, workspace_members, audit_logs.
Partial unique indexes keep email/slug unique among non-deleted rows only.

Revision ID: 0002_identity
Revises: 0001_baseline
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_identity"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'platform_admin', 'system')",
            name=op.f("ck_audit_logs_actor_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        schema="core",
    )
    op.create_index(
        "ix_audit_logs_actor_occurred",
        "audit_logs",
        ["actor_user_id", sa.literal_column("occurred_at DESC")],
        unique=False,
        schema="core",
    )
    op.create_index(
        "ix_audit_logs_workspace_occurred",
        "audit_logs",
        ["workspace_id", sa.literal_column("occurred_at DESC")],
        unique=False,
        schema="core",
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(length=200), server_default="", nullable=False),
        sa.Column(
            "is_platform_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f("ck_users_status")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        schema="core",
    )
    op.create_index(
        "uq_users_email_live",
        "users",
        ["email"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
        schema="core",
    )
    op.create_index(
        "ix_user_sessions_absolute_expires_at",
        "user_sessions",
        ["absolute_expires_at"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False, schema="core"
    )
    op.create_table(
        "workspaces",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Kolkata", nullable=False),
        sa.Column("base_currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("fiscal_year_start_month", sa.SmallInteger(), server_default="4", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            "base_currency ~ '^[A-Z]{3}$'", name=op.f("ck_workspaces_base_currency")
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_workspaces_slug_format")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'archived')", name=op.f("ck_workspaces_status")
        ),
        sa.CheckConstraint(
            "fiscal_year_start_month BETWEEN 1 AND 12",
            name=op.f("ck_workspaces_fiscal_year_start_month"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["core.users.id"],
            name=op.f("fk_workspaces_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        schema="core",
    )
    op.create_index(
        "uq_workspaces_slug_live",
        "workspaces",
        ["slug"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("added_by", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')", name=op.f("ck_workspace_members_role")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'removed')", name=op.f("ck_workspace_members_status")
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["core.users.id"],
            name=op.f("fk_workspace_members_added_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_workspace_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["core.workspaces.id"],
            name=op.f("fk_workspace_members_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_members")),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name=op.f("uq_workspace_members_workspace_id_user_id")
        ),
        schema="core",
    )
    op.create_index(
        "ix_workspace_members_user_id",
        "workspace_members",
        ["user_id"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members", schema="core")
    op.drop_table("workspace_members", schema="core")
    op.drop_index(
        "uq_workspaces_slug_live",
        table_name="workspaces",
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("workspaces", schema="core")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions", schema="core")
    op.drop_index("ix_user_sessions_absolute_expires_at", table_name="user_sessions", schema="core")
    op.drop_table("user_sessions", schema="core")
    op.drop_index(
        "uq_users_email_live",
        table_name="users",
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("users", schema="core")
    op.drop_index("ix_audit_logs_workspace_occurred", table_name="audit_logs", schema="core")
    op.drop_index("ix_audit_logs_actor_occurred", table_name="audit_logs", schema="core")
    op.drop_table("audit_logs", schema="core")
