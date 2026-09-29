"""All SQL for sync runs and dataset freshness. Every read is scoped to a connection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import ConnectionScope
from clario.platform.integrations.contract import IngestResult
from clario.platform.sync.models import ConnectionDataset, DatasetStatus, RunStatus, SyncRun


def _mine(scope: ConnectionScope) -> list[ColumnElement[bool]]:
    return [
        SyncRun.connection_id == scope.connection_id,
        SyncRun.workspace_id == scope.workspace_id,
    ]


async def reap_stale(session: AsyncSession, started_before: datetime, now: datetime) -> int:
    """Runs still 'running' long after they started died with their process: mark them failed."""
    result = await session.execute(
        update(SyncRun)
        .where(SyncRun.status == RunStatus.RUNNING, SyncRun.started_at < started_before)
        .values(status=RunStatus.FAILED, finished_at=now, error_code="sync.abandoned")
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def running_run(session: AsyncSession, scope: ConnectionScope) -> SyncRun | None:
    return await session.scalar(
        select(SyncRun).where(*_mine(scope), SyncRun.status == RunStatus.RUNNING)
    )


async def latest_run(session: AsyncSession, scope: ConnectionScope) -> SyncRun | None:
    return await session.scalar(
        select(SyncRun)
        .where(*_mine(scope))
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    )


async def get_run(
    session: AsyncSession, scope: ConnectionScope, run_id: uuid.UUID
) -> SyncRun | None:
    return await session.scalar(select(SyncRun).where(*_mine(scope), SyncRun.id == run_id))


async def datasets(session: AsyncSession, scope: ConnectionScope) -> dict[str, ConnectionDataset]:
    rows = await session.scalars(
        select(ConnectionDataset)
        .where(
            ConnectionDataset.connection_id == scope.connection_id,
            ConnectionDataset.workspace_id == scope.workspace_id,
        )
        .execution_options(populate_existing=True)
    )
    return {row.dataset: row for row in rows}


async def record_dataset(
    session: AsyncSession,
    scope: ConnectionScope,
    key: str,
    run_id: uuid.UUID,
    now: datetime,
    *,
    result: IngestResult | None,
    error_code: str | None = None,
) -> None:
    """Upsert freshness. A failure keeps the last success time, window and count."""
    ok = result is not None
    values: dict[str, object] = {
        "status": DatasetStatus.OK if ok else DatasetStatus.FAILED,
        "last_attempt_at": now,
        "last_run_id": run_id,
        "last_error_code": None if ok else error_code,
    }
    if result is not None:
        values |= {
            "last_success_at": now,
            "window_start": result.window_start,
            "window_end": result.window_end,
            "row_count": result.row_count,
        }
    statement = insert(ConnectionDataset).values(
        connection_id=scope.connection_id, workspace_id=scope.workspace_id, dataset=key, **values
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[ConnectionDataset.connection_id, ConnectionDataset.dataset],
            set_={k: statement.excluded[k] for k in values},
        )
    )


async def delete_datasets(session: AsyncSession, scope: ConnectionScope) -> None:
    await session.execute(
        delete(ConnectionDataset).where(
            ConnectionDataset.connection_id == scope.connection_id,
            ConnectionDataset.workspace_id == scope.workspace_id,
        )
    )
