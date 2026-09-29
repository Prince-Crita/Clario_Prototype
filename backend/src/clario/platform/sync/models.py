"""Sync bookkeeping in `core` (plan §14.2, §31): runs, and freshness per dataset."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from clario.core.db import Base, UUIDPrimaryKey

SCHEMA = "core"
CONNECTION_FK = ["core.integration_connections.id", "core.integration_connections.workspace_id"]


class SyncTrigger(StrEnum):
    INITIAL = "initial"  # right after an account is chosen
    MANUAL = "manual"  # "Refresh now" (cooldown applies)
    STALE = "stale"  # data older than FINANCE_STALE_AFTER_MINUTES when a view opens
    SCHEDULED = "scheduled"  # reserved for `clario sync due` (cron), and the operator CLI


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"  # some datasets failed; they keep their last good data
    FAILED = "failed"


class DatasetStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class SyncRun(UUIDPrimaryKey, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            CONNECTION_FK,
            name="fk_sync_runs_connection",
            ondelete="CASCADE",
        ),
        CheckConstraint("trigger IN ('initial', 'manual', 'stale', 'scheduled')", name="trigger"),
        CheckConstraint("status IN ('running', 'succeeded', 'partial', 'failed')", name="status"),
        Index("ix_sync_runs_connection_id_started_at", "connection_id", text("started_at DESC")),
        {"schema": SCHEMA},
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column()
    connection_id: Mapped[uuid.UUID] = mapped_column()
    trigger: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.RUNNING)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    api_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)


class ConnectionDataset(Base):
    """Freshness of one dataset of one connection: what the UI's "data as of" is built from."""

    __tablename__ = "connection_datasets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            CONNECTION_FK,
            name="fk_connection_datasets_connection",
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('ok', 'failed')", name="status"),
        {"schema": SCHEMA},
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(16))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("core.sync_runs.id", ondelete="SET NULL")
    )
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    row_count: Mapped[int | None] = mapped_column(Integer)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
