"""Per-tenant Zoho OAuth client credentials.

Revision ID: 0002_tenant_zoho_oauth_app
Revises: 0001_multi_tenant
Create Date: 2026-09-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_tenant_zoho_oauth_app"
down_revision: Union[str, None] = "0001_multi_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "zoho_connections",
        sa.Column("oauth_client_id", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "zoho_connections",
        sa.Column("encrypted_oauth_client_secret", sa.Text(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("zoho_connections", "encrypted_oauth_client_secret")
    op.drop_column("zoho_connections", "oauth_client_id")
