"""Integration catalog and per-workspace visibility (Phase 4; plan §15).

`core.integrations` mirrors the code manifests (upserted at startup);
`core.workspace_integrations` holds explicit card visibility per workspace.

Revision ID: 0003_integrations
Revises: 0002_identity
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_integrations"
down_revision: str | None = "0002_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("vendor", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default="100", nullable=False),
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
            "availability IN ('available', 'coming_soon', 'retired')",
            name=op.f("ck_integrations_availability"),
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_integrations")),
        schema="core",
    )
    op.create_table(
        "workspace_integrations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("integration_key", sa.String(length=64), nullable=False),
        sa.Column("is_visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["integration_key"],
            ["core.integrations.key"],
            name=op.f("fk_workspace_integrations_integration_key_integrations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["core.workspaces.id"],
            name=op.f("fk_workspace_integrations_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "workspace_id", "integration_key", name=op.f("pk_workspace_integrations")
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("workspace_integrations", schema="core")
    op.drop_table("integrations", schema="core")
