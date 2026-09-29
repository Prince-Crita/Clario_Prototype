"""Baseline: ownership schemas for Clario Core and the Finance domain (plan §14.1).

Tables arrive with their modules (identity/workspaces in Phase 2, finance.* in Phase 6).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("core", "finance")


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        op.execute(f"COMMENT ON SCHEMA {schema} IS 'Clario: owned by the {schema} module'")


def downgrade() -> None:
    # `core` also holds alembic_version, so only schemas without other objects are dropped.
    op.execute("DROP SCHEMA IF EXISTS finance RESTRICT")
