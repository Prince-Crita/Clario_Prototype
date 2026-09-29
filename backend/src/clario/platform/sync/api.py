"""Freshness routes: see how current a connection's mirror is, and ask for a refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections.deps import ViewConnection
from clario.platform.sync import repository as repo
from clario.platform.sync.models import RunStatus, SyncRun, SyncTrigger
from clario.platform.sync.schemas import DatasetStatusOut, SyncRequest, SyncRunOut, SyncStatus
from clario.platform.sync.service import SyncRunner
from clario.platform.web import SessionDep

router = APIRouter(tags=["sync"])
PATH = "/workspaces/{workspace_id}/connections/{connection_id}/sync"


def runner_of(request: Request) -> SyncRunner:
    runner: SyncRunner = request.app.state.sync
    return runner


def _run_out(run: SyncRun | None) -> SyncRunOut | None:
    if run is None:
        return None
    return SyncRunOut(
        id=run.id,
        trigger=run.trigger,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        api_calls=run.api_calls,
        error_code=run.error_code,
    )


async def build_status(
    session: AsyncSession, runner: SyncRunner, scope: ConnectionScope
) -> SyncStatus:
    domain = runner.domain_for(scope)
    rows = await repo.datasets(session, scope)
    running = await repo.running_run(session, scope)
    run = running or await repo.latest_run(session, scope)
    datasets = []
    for dataset in domain.datasets if domain else ():
        row = rows.get(dataset.key)
        datasets.append(
            DatasetStatusOut(
                key=dataset.key,
                label=dataset.label,
                status=row.status if row else "never",
                last_success_at=row.last_success_at if row else None,
                last_attempt_at=row.last_attempt_at if row else None,
                row_count=row.row_count if row else None,
                window_start=row.window_start if row else None,
                window_end=row.window_end if row else None,
                error_code=row.last_error_code if row else None,
            )
        )
    successes = [d.last_success_at for d in datasets]
    as_of = min(successes) if successes and all(successes) else None  # type: ignore[type-var]
    return SyncStatus(
        state="running" if running and running.status == RunStatus.RUNNING else "idle",
        as_of=as_of,
        run=_run_out(run),
        datasets=datasets,
    )


@router.get(PATH, response_model=SyncStatus, summary="How current this connection's data is")
async def get_sync(scope: ViewConnection, session: SessionDep, request: Request) -> SyncStatus:
    return await build_status(session, runner_of(request), scope)


@router.post(
    PATH,
    response_model=SyncStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Refresh this connection's data (runs in the background)",
    responses={
        409: {"description": "Not connected, or needs reconnecting"},
        429: {"description": "Cooldown, or the provider's daily budget is nearly used up"},
    },
)
async def request_sync(
    scope: ViewConnection,
    session: SessionDep,
    request: Request,
    body: Annotated[SyncRequest | None, Body()] = None,
) -> SyncStatus:
    runner = runner_of(request)
    mode = body.mode if body else "manual"
    trigger = SyncTrigger.MANUAL if mode == "manual" else SyncTrigger.STALE
    await runner.trigger(scope, trigger, requested_by=scope.user_id)
    return await build_status(session, runner, scope)
