"""Catalog and per-workspace visibility tables in `core` (plan §14.2, §15.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, Timestamps

SCHEMA = "core"


class IntegrationRecord(Timestamps, Base):
    """Mirror of the code manifests (upserted at startup) — the FK target for workspace data."""

    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint(
            "availability IN ('available', 'coming_soon', 'retired')", name="availability"
        ),
        {"schema": SCHEMA},
    )

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    vendor: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    availability: Mapped[str] = mapped_column(String(16))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=100, server_default="100")


class WorkspaceIntegration(Timestamps, Base):
    """Explicit visibility of one integration card for one workspace.

    Without a row: available integrations are visible, coming-soon ones are hidden.
    A row overrides that default in either direction.
    """

    __tablename__ = "workspace_integrations"
    __table_args__ = ({"schema": SCHEMA},)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("core.workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    integration_key: Mapped[str] = mapped_column(
        ForeignKey("core.integrations.key", ondelete="CASCADE"), primary_key=True
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
