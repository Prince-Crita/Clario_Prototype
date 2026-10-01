"""The sync engine (plan §31): an on-demand mirror, refreshed on connect, when stale, or on request.

How a run works:
  * `trigger` locks the connection row, reaps abandoned runs, and either joins the run already in
    progress or records a new `running` run and starts it in the background. Across workers the
    row lock serialises triggers, and a PostgreSQL advisory lock guarantees one run per connection.
  * Each dataset (declared by the connection's domain, in order) is written in **its own
    transaction** holding a KEY SHARE lock on the connection row: a disconnect waits for it, so
    a write can never land after a purge, while status updates such as needs_reauth still pass.
    A failed dataset keeps its last good data; the run ends `partial`.
    `connection.needs_reauth` or a vanished connection stop the run.
  * The run records its API calls; the source's rate-limit reading is kept on the connection so a
    nearly exhausted daily budget blocks optional refreshes (plan §16.4).
No queues or workers (ADR-014): runs are asyncio tasks in the API process; `clario sync run` runs
one inline.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import today_in, utc_now
from clario.core.db import Database
from clario.core.errors import ClarioError, ConflictError, NotFoundError, RateLimitedError
from clario.core.logs import redact_text
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections import repository as connection_repo
from clario.platform.connections.models import Connection, ConnectionStatus
from clario.platform.connections.service import connection_profile
from clario.platform.integrations.contract import (
    ConnectionContext,
    Dataset,
    DomainModule,
    IngestContext,
)
from clario.platform.integrations.registry import Registry
from clario.platform.sync import repository as repo
from clario.platform.sync.models import RunStatus, SyncRun, SyncTrigger
from clario.settings import Settings

logger = logging.getLogger(__name__)

ABANDONED_AFTER = timedelta(minutes=15)
BUDGET_FLOOR = 0.10  # keep the last 10% of the provider's daily call budget for essential syncs
STOP_CODES = frozenset({"connection.needs_reauth", "sync.connection_gone"})


class _ConnectionGoneError(Exception):
    """The connection was disconnected (or stopped being connected) during the run."""


@dataclass(frozen=True, slots=True)
class TriggerOutcome:
    run: SyncRun | None
    started: bool


def _lock_key(connection_id: uuid.UUID) -> int:
    return int.from_bytes(connection_id.bytes[:8], "big", signed=True)


def _budget_low(connection: Connection, now: datetime) -> bool:
    reading: dict[str, Any] = (connection.settings or {}).get("rate_limit") or {}
    limit, remaining = reading.get("limit"), reading.get("remaining")
    if not isinstance(limit, int) or not isinstance(remaining, int) or limit <= 0:
        return False
    reset_at = reading.get("reset_at")
    if isinstance(reset_at, str) and datetime.fromisoformat(reset_at) <= now:
        return False  # the budget has been renewed since this reading
    return remaining / limit < BUDGET_FLOOR


class SyncRunner:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        registry: Registry,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.database = database
        self.settings = settings
        self.registry = registry
        self.clock = clock  # tests pin "today"; everything time-based reads it
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}

    def domain_for(self, scope: ConnectionScope) -> DomainModule | None:
        return self.registry.domain(scope.domain)

    # ------------------------------------------------------------ freshness

    async def is_fresh(self, session: AsyncSession, scope: ConnectionScope, now: datetime) -> bool:
        domain = self.domain_for(scope)
        keys = [d.key for d in domain.datasets] if domain else []
        rows = await repo.datasets(session, scope)
        cutoff = now - timedelta(minutes=self.settings.finance_stale_after_minutes)
        return bool(keys) and all(
            (row := rows.get(k)) is not None
            and row.last_success_at is not None
            and row.last_success_at > cutoff
            for k in keys
        )

    # ------------------------------------------------------------ trigger

    async def trigger(
        self,
        scope: ConnectionScope,
        trigger: SyncTrigger,
        requested_by: uuid.UUID | None = None,
    ) -> TriggerOutcome:
        """Start a run, join the one in progress, or (for `stale`) do nothing when fresh."""
        now = self.clock()
        async with self.database.sessions() as session:
            await repo.reap_stale(session, now - ABANDONED_AFTER, now)
            connection = await connection_repo.lock_live(session, scope, "no_key_update")
            if connection is None:
                raise NotFoundError("Connection not found.", code="connection.not_found")
            if connection.status != ConnectionStatus.CONNECTED:
                code = (
                    "connection.needs_reauth"
                    if connection.status == ConnectionStatus.NEEDS_REAUTH
                    else "connection.not_connected"
                )
                raise ConflictError("Connect this integration before refreshing it.", code=code)
            running = await repo.running_run(session, scope)
            if running is not None:
                await session.commit()
                return TriggerOutcome(run=running, started=False)
            if trigger is not SyncTrigger.INITIAL:
                refusal = await self._refusal(session, scope, connection, trigger, now)
                if refusal is not None:
                    await session.commit()
                    if trigger is SyncTrigger.STALE:
                        return TriggerOutcome(
                            run=await repo.latest_run(session, scope), started=False
                        )
                    raise refusal
            run = SyncRun(
                workspace_id=scope.workspace_id,
                connection_id=scope.connection_id,
                trigger=trigger,
                status=RunStatus.RUNNING,
                requested_by=requested_by,
                started_at=now,
            )
            session.add(run)
            await session.commit()
        if self.settings.sync_inline:
            # Serverless: a function may be frozen once its response is sent, so the import must
            # finish inside the request. `execute` never raises; the run records any failure.
            await self.execute(run.id, scope)
        else:
            self._start(run.id, scope)
        return TriggerOutcome(run=run, started=True)

    async def _refusal(
        self,
        session: AsyncSession,
        scope: ConnectionScope,
        connection: Connection,
        trigger: SyncTrigger,
        now: datetime,
    ) -> ClarioError | None:
        if trigger is SyncTrigger.STALE and await self.is_fresh(session, scope, now):
            return ConflictError("Data is fresh.", code="sync.fresh")
        if trigger is SyncTrigger.MANUAL:
            latest = await repo.latest_run(session, scope)
            cooldown = timedelta(seconds=self.settings.finance_refresh_cooldown_seconds)
            if latest is not None and now - latest.started_at < cooldown:
                wait = int((latest.started_at + cooldown - now).total_seconds()) + 1
                return RateLimitedError(
                    "Data was refreshed moments ago. Try again in a minute.",
                    code="sync.cooldown",
                    extra={"retry_after_seconds": wait},
                )
        if _budget_low(connection, now):
            return RateLimitedError(
                "The connected system's daily request limit is nearly used up. "
                "Clario will refresh again after it resets.",
                code="sync.budget_low",
            )
        return None

    def _start(self, run_id: uuid.UUID, scope: ConnectionScope) -> None:
        task = asyncio.create_task(self.execute(run_id, scope), name=f"sync-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))

    async def start_quietly(
        self, scope: ConnectionScope, trigger: SyncTrigger, requested_by: uuid.UUID | None
    ) -> None:
        """Fire-and-forget trigger (e.g. the initial import after connecting)."""
        try:
            await self.trigger(scope, trigger, requested_by)
        except ClarioError as exc:
            logger.info("Sync not started", extra={"reason": exc.code})

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)

    async def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        await self.wait_idle()

    # ------------------------------------------------------------ run

    async def execute(self, run_id: uuid.UUID, scope: ConnectionScope) -> None:
        """Run every dataset of the connection's domain. Never raises (the run records failures)."""
        async with self.database.engine.connect() as lock:
            if not await lock.scalar(
                select(func.pg_try_advisory_lock(_lock_key(scope.connection_id)))
            ):
                await self._finish(scope, run_id, RunStatus.FAILED, 0, None, "sync.busy")
                return
            try:
                await self._run(run_id, scope)
            except asyncio.CancelledError:
                await self._finish(scope, run_id, RunStatus.FAILED, 0, None, "sync.cancelled")
                raise
            except Exception as exc:
                logger.exception("Sync run crashed", extra={"run_id": str(run_id)})
                await self._finish(
                    scope, run_id, RunStatus.FAILED, 0, None, "sync.crashed", repr(exc)
                )
            finally:
                await lock.execute(select(func.pg_advisory_unlock(_lock_key(scope.connection_id))))
                await lock.commit()

    async def _run(self, run_id: uuid.UUID, scope: ConnectionScope) -> None:
        domain = self.domain_for(scope)
        plugin = self.registry.plugin(scope.integration_key)
        async with self.database.sessions() as session:
            connection = await connection_repo.get_live(session, scope, scope.connection_id)
        if connection is None or domain is None:
            await self._finish(scope, run_id, RunStatus.FAILED, 0, None, "sync.connection_gone")
            return
        tz, fiscal_month = connection_profile(connection, scope)
        today = today_in(tz, self.clock())

        failures: dict[str, str] = {}
        async with self.database.sessions() as source_session:
            context = ConnectionContext(scope=scope, session=source_session, settings=self.settings)
            source = domain.fixture_source(self.settings) if domain.fixture_source else None
            if source is None and plugin is None:
                await self._finish(
                    scope, run_id, RunStatus.FAILED, 0, None, "integration.not_available"
                )
                return
            source = source if source is not None else plugin.data_source(context)  # type: ignore[union-attr]
            try:
                for dataset in domain.datasets:
                    code = await self._ingest(dataset, source, run_id, scope, today, fiscal_month)
                    if code is not None:
                        failures[dataset.key] = code
                        if code in STOP_CODES:
                            break
            finally:
                closer = getattr(source, "aclose", None)
                if closer is not None:
                    await closer()

        written = len(domain.datasets) - len(failures)
        stopped = any(code in STOP_CODES for code in failures.values())
        status = (
            RunStatus.SUCCEEDED
            if not failures
            else RunStatus.FAILED
            if stopped or written == 0
            else RunStatus.PARTIAL
        )
        await self._finish(
            scope,
            run_id,
            status,
            int(getattr(source, "api_calls", 0)),
            getattr(source, "rate_limit", None),
            next(iter(failures.values()), None),
            ", ".join(f"{k}: {v}" for k, v in failures.items()) or None,
        )

    async def _ingest(
        self,
        dataset: Dataset,
        source: object,
        run_id: uuid.UUID,
        scope: ConnectionScope,
        today: Any,
        fiscal_month: int,
    ) -> str | None:
        """Write one dataset in its own transaction. Returns an error code, or None on success."""
        async with self.database.sessions() as session:
            try:
                connection = await connection_repo.lock_live(session, scope, "key_share")
                if connection is None or connection.status != ConnectionStatus.CONNECTED:
                    raise _ConnectionGoneError
                result = await dataset.ingest(
                    IngestContext(
                        session=session,
                        scope=scope,
                        source=source,
                        run_id=run_id,
                        today=today,
                        fiscal_year_start_month=fiscal_month,
                    )
                )
                await repo.record_dataset(
                    session, scope, dataset.key, run_id, self.clock(), result=result
                )
                await session.commit()
                return None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await session.rollback()
                if isinstance(exc, _ConnectionGoneError):
                    return "sync.connection_gone"
                code = exc.code if isinstance(exc, ClarioError) else "sync.dataset_failed"
                logger.warning(
                    "Dataset failed; its last good data is kept",
                    extra={"dataset": dataset.key, "error_code": code},
                    exc_info=not isinstance(exc, ClarioError),
                )
        async with self.database.sessions() as session:
            await repo.record_dataset(
                session, scope, dataset.key, run_id, self.clock(), result=None, error_code=code
            )
            await session.commit()
        return code

    async def _finish(
        self,
        scope: ConnectionScope,
        run_id: uuid.UUID,
        status: RunStatus,
        api_calls: int,
        rate_limit: dict[str, Any] | None,
        error_code: str | None,
        error_detail: str | None = None,
    ) -> None:
        async with self.database.sessions() as session:
            run = await repo.get_run(session, scope, run_id)
            if run is None:
                return
            run.status = status
            run.finished_at = self.clock()
            run.api_calls = api_calls
            run.error_code = error_code
            run.error_detail = redact_text(error_detail)[:1000] if error_detail else None
            if rate_limit:
                connection = await connection_repo.get_live(session, scope, scope.connection_id)
                if connection is not None:
                    connection.settings = {**(connection.settings or {}), "rate_limit": rate_limit}
            await session.commit()
        logger.info(
            "Sync run finished",
            extra={"run_id": str(run_id), "status": status.value, "api_calls": api_calls},
        )
