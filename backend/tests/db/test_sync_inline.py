"""SYNC_INLINE (serverless hosting): the import has finished by the time `trigger` returns.

Normally a refresh starts a background task and the response goes out while it runs. On a
serverless function that task may never get to finish, so with `sync_inline` the work completes
inside the request instead. The rest of the engine (locks, cooldown, per-dataset transactions) is
unchanged and covered by test_sync.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI

from clario.platform.access.scopes import ConnectionScope
from clario.platform.sync.models import RunStatus, SyncRun, SyncTrigger
from clario.platform.sync.service import SyncRunner
from tests.support import Factory, zoho_connection

pytestmark = pytest.mark.db

OWNER = "owner@inline.test"
NOW = datetime(2026, 9, 25, 10, 26, tzinfo=UTC)


async def _connection(factory: Factory, app: FastAPI) -> tuple[ConnectionScope, SyncRunner]:
    await factory.user(OWNER)
    workspace = await factory.workspace("Inline Traders", OWNER)
    scope = await zoho_connection(factory, app.state.settings, workspace, OWNER)
    app.state.settings.finance_fixture_source = True  # fixture data instead of Zoho
    runner: SyncRunner = app.state.sync
    runner.clock = lambda: NOW
    return scope, runner


async def _status(app: FastAPI, run: SyncRun) -> str:
    async with app.state.database.sessions() as session:
        stored = await session.get(SyncRun, run.id)
    assert stored is not None
    return str(stored.status)  # stored as text; RunStatus is a StrEnum, so == compares fine


async def test_inline_run_is_finished_when_trigger_returns(
    factory: Factory, db_app: FastAPI
) -> None:
    scope, runner = await _connection(factory, db_app)
    db_app.state.settings.sync_inline = True

    outcome = await runner.trigger(scope, SyncTrigger.SCHEDULED)

    assert outcome.started
    assert not runner._tasks  # nothing is left running after the response
    assert await _status(db_app, outcome.run) == RunStatus.SUCCEEDED  # without wait_idle()


async def test_default_run_continues_in_the_background(factory: Factory, db_app: FastAPI) -> None:
    scope, runner = await _connection(factory, db_app)
    assert db_app.state.settings.sync_inline is False  # the default: behaviour is unchanged

    outcome = await runner.trigger(scope, SyncTrigger.SCHEDULED)
    assert outcome.started
    await runner.wait_idle()  # only here has the background task finished

    assert await _status(db_app, outcome.run) == RunStatus.SUCCEEDED
