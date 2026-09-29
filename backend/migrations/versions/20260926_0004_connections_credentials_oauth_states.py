"""Integration connections, encrypted credentials and OAuth states (Phase 5; plan §14.2, §17).

* `integration_connections`: one live connection per workspace and integration (partial unique
  index); `(id, workspace_id)` unique for composite tenant FKs.
* `connection_credentials`: encrypted secret, composite FK to its connection (same workspace).
* `oauth_states`: SHA-256 of single-use consent states.

Revision ID: 0004_connections
Revises: 0003_integrations
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_connections"
down_revision: str | None = "0003_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("integration_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=True),
        sa.Column("external_account_name", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=16), nullable=True),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("connected_by", sa.Uuid(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'connected', 'needs_reauth', 'error', 'disconnected')",
            name=op.f("ck_integration_connections_status"),
        ),
        sa.ForeignKeyConstraint(
            ["connected_by"],
            ["core.users.id"],
            name=op.f("fk_integration_connections_connected_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["integration_key"],
            ["core.integrations.key"],
            name=op.f("fk_integration_connections_integration_key_integrations"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["core.workspaces.id"],
            name=op.f("fk_integration_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_connections")),
        sa.UniqueConstraint(
            "id", "workspace_id", name="uq_integration_connections_id_workspace_id"
        ),
        schema="core",
    )
    op.create_index(
        "uq_integration_connections_live",
        "integration_connections",
        ["workspace_id", "integration_key"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "connection_credentials",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_id", sa.String(length=16), nullable=False),
        sa.Column(
            "granted_scopes",
            postgresql.ARRAY(sa.String(length=128)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
        sa.CheckConstraint("kind IN ('oauth2')", name=op.f("ck_connection_credentials_kind")),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["core.integration_connections.id", "core.integration_connections.workspace_id"],
            name="fk_connection_credentials_connection",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connection_id", name=op.f("pk_connection_credentials")),
        schema="core",
    )
    op.create_table(
        "oauth_states",
        sa.Column("state_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("integration_key", sa.String(length=64), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("region", sa.String(length=16), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["core.integration_connections.id"],
            name=op.f("fk_oauth_states_connection_id_integration_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_oauth_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["core.workspaces.id"],
            name=op.f("fk_oauth_states_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_states")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_oauth_states_state_hash")),
        schema="core",
    )
    op.create_index(
        "ix_oauth_states_expires_at", "oauth_states", ["expires_at"], unique=False, schema="core"
    )


def downgrade() -> None:
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states", schema="core")
    op.drop_table("oauth_states", schema="core")
    op.drop_table("connection_credentials", schema="core")
    op.drop_index(
        "uq_integration_connections_live",
        table_name="integration_connections",
        schema="core",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_table("integration_connections", schema="core")
