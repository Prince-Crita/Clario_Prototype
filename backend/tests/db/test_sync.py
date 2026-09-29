"""Phase 6 exit criteria: a full sync of the organisation mirrors every dataset, counts match what
Zoho returned, and nothing is ever silently truncated. Plus the engine's rules (plan §31): per-
dataset transactions, last good data kept, one run per connection, cooldown, freshness, budget,
the reaper, needs_reauth, purge on disconnect, and tenant-safe rows.

Zoho is mocked with respx from the sanitised Phase 0 TEST responses (tests/fixtures/zoho_books);
"today" is pinned so the windows never drift.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from clario.platform.access.permissions import Role
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections import vault
from clario.platform.sync.models import SyncTrigger
from clario.platform.sync.service import SyncRunner, _lock_key
from tests.support import ZOHO_ORG_ID, Factory, login, zoho_connection

pytestmark = pytest.mark.db

OWNER = "owner@alpha.test"
API = "https://www.zohoapis.in/books/v3"
FIXTURES = Path(__file__).parents[1] / "fixtures" / "zoho_books"
NOW = datetime(2026, 9, 26, 6, 30, tzinfo=UTC)  # 12:00 IST; windows: 1 Apr 2025 – 26 Sep 2026
EXPECTED_ROWS = {
    "accounts": 67,
    "parties": 4,  # 3 customers + 1 vendor
    "invoices": 7,
    "payments_received": 3,
    "expenses": 4,
    "payments_made": 1,
    "ledger_monthly": 9,
    "balances": 5,
}
EXPECTED_CALLS = 1 + 2 + 1 + 1 + 1 + 1 + 18 + 1  # accounts, contacts ×2, lists, 18 months, BS


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


def pnl(request: httpx.Request) -> httpx.Response:
    month = request.url.params["from_date"][:7].replace("-", "_")
    path = FIXTURES / f"pnl_{month}.json"
    body = (
        fixture(f"pnl_{month}")
        if path.exists()
        else {
            "code": 0,
            "page_context": {"report_basis": "Accrual"},
            "profit_and_loss": [],
        }
    )
    return httpx.Response(
        200,
        json=body,
        headers={
            "x-rate-limit-limit": "1000",
            "x-rate-limit-remaining": "900",
            "x-rate-limit-reset": "3600",
        },
    )


def contacts(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=fixture(f"contacts_{request.url.params['contact_type']}"))


@pytest.fixture
def zoho() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        for name in (
            "chartofaccounts",
            "invoices",
            "customerpayments",
            "expenses",
            "vendorpayments",
        ):
            router.get(f"{API}/{name}", name=name).mock(
                return_value=httpx.Response(200, json=fixture(name))
            )
        router.get(f"{API}/contacts", name="contacts").mock(side_effect=contacts)
        router.get(f"{API}/reports/profitandloss", name="pnl").mock(side_effect=pnl)
        router.get(f"{API}/reports/balancesheet", name="balancesheet").mock(
            return_value=httpx.Response(200, json=fixture("balancesheet"))
        )
        yield router


@pytest.fixture
def runner(db_app: FastAPI) -> SyncRunner:
    sync: SyncRunner = db_app.state.sync
    sync.clock = lambda: NOW
    return sync


@pytest.fixture
async def connected(factory: Factory, db_app: FastAPI) -> ConnectionScope:
    await factory.user(OWNER)
    workspace = await factory.workspace("Alpha Traders", OWNER)
    return await zoho_connection(factory, db_app.state.settings, workspace, OWNER)


async def sync_now(runner: SyncRunner, scope: ConnectionScope) -> None:
    outcome = await runner.trigger(scope, SyncTrigger.SCHEDULED)
    assert outcome.started
    await runner.wait_idle()


async def status(client: AsyncClient, scope: ConnectionScope) -> dict[str, Any]:
    response = await client.get(
        f"/api/v1/workspaces/{scope.workspace_id}/connections/{scope.connection_id}/sync"
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def counts(body: dict[str, Any]) -> dict[str, Any]:
    return {d["key"]: d["row_count"] for d in body["datasets"]}


async def one(factory: Factory, sql: str, **params: Any) -> Any:
    rows = await factory.sql(sql, **params)
    assert rows is not None
    return rows[0][0]


# ---------------------------------------------------------------- the exit criterion


async def test_full_sync_mirrors_every_dataset_and_counts_match_zoho(
    connected: ConnectionScope,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
    db_client: AsyncClient,
) -> None:
    csrf = await login(db_client, OWNER)
    url = f"/api/v1/workspaces/{connected.workspace_id}/connections/{connected.connection_id}/sync"
    started = await db_client.post(url, headers={"X-CSRF-Token": csrf}, json={"mode": "manual"})
    assert started.status_code == 202, started.text
    await runner.wait_idle()

    body = await status(db_client, connected)
    assert body["state"] == "idle"
    assert body["run"]["status"] == "succeeded"
    assert body["run"]["api_calls"] == EXPECTED_CALLS
    assert counts(body) == EXPECTED_ROWS
    assert all(d["status"] == "ok" for d in body["datasets"])
    assert body["as_of"] is not None
    payments = next(d for d in body["datasets"] if d["key"] == "payments_received")
    assert (payments["window_start"], payments["window_end"]) == ("2025-04-01", "2026-09-26")

    # Every call was scoped to the chosen organisation; the P&L was fetched month by month.
    assert all(c.request.url.params["organization_id"] == ZOHO_ORG_ID for c in zoho.calls)
    assert zoho.routes["pnl"].call_count == 18

    # The mirror holds exactly what Zoho returned, with references and lineage resolved.
    for table, expected in (
        ("finance.accounts", 67),
        ("finance.invoices", 7),
        ("finance.balance_snapshots", 5),
    ):
        assert await one(factory, f"SELECT count(*) FROM {table}") == expected  # noqa: S608
    assert await one(factory, "SELECT count(*) FROM finance.invoices WHERE party_id IS NULL") == 0
    assert await one(factory, "SELECT count(*) FROM finance.expenses WHERE account_id IS NULL") == 0
    receivables = await one(
        factory,
        "SELECT sum(balance_base) FROM finance.invoices WHERE status NOT IN ('draft', 'void')",
    )
    assert receivables == Decimal("43000")
    cash_and_bank = await one(
        factory,
        "SELECT sum(balance) FROM finance.balance_snapshots "
        "WHERE account_group IN ('Cash', 'Bank')",
    )
    assert cash_and_bank == Decimal("5500")
    revenue_fy = await one(
        factory,
        "SELECT sum(amount) FROM finance.ledger_monthly_amounts "
        "WHERE section = 'operating_income' AND period_month >= '2026-04-01'",
    )
    assert revenue_fy == Decimal("108000")  # = billed this FY excluding draft/void (Phase 0)
    lineage = await factory.sql(
        "SELECT DISTINCT source_system, sync_run_id::text, workspace_id FROM finance.invoices"
    )
    assert lineage == [("zoho-books", body["run"]["id"], connected.workspace_id)]
    rate = await one(
        factory, "SELECT settings->'rate_limit'->>'remaining' FROM core.integration_connections"
    )
    assert rate == "900"


async def test_resync_is_idempotent_keeps_ids_and_reflects_deletions(
    connected: ConnectionScope, runner: SyncRunner, zoho: respx.MockRouter, factory: Factory
) -> None:
    await sync_now(runner, connected)
    ids_before = dict(await factory.sql("SELECT source_record_id, id FROM finance.parties") or [])

    invoices = fixture("invoices")
    invoices["invoices"] = [i for i in invoices["invoices"] if i["invoice_number"] != "INV-000007"]
    zoho.routes["invoices"].mock(return_value=httpx.Response(200, json=invoices))
    payments = fixture("customerpayments")
    payments["customerpayments"][0]["bcy_amount"] = 51000
    zoho.routes["customerpayments"].mock(return_value=httpx.Response(200, json=payments))
    await sync_now(runner, connected)

    assert await one(factory, "SELECT count(*) FROM finance.invoices") == 6  # deleted in Zoho
    assert await one(factory, "SELECT count(*) FROM finance.accounts") == 67  # no duplicates
    ids_after = dict(await factory.sql("SELECT source_record_id, id FROM finance.parties") or [])
    assert ids_after == ids_before  # stable ids: references survive re-syncs
    assert await one(factory, "SELECT max(amount_base) FROM finance.payments_received") == Decimal(
        "51000"
    )


# ---------------------------------------------------------------- failures


async def test_page_ceiling_fails_the_dataset_instead_of_truncating(
    connected: ConnectionScope,
    db_app: FastAPI,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
    db_client: AsyncClient,
) -> None:
    db_app.state.settings.zoho_max_pages = 1
    more = fixture("invoices")
    more["page_context"]["has_more_page"] = True
    zoho.routes["invoices"].mock(return_value=httpx.Response(200, json=more))
    await sync_now(runner, connected)

    await login(db_client, OWNER)
    body = await status(db_client, connected)
    assert body["run"]["status"] == "partial"
    invoices = next(d for d in body["datasets"] if d["key"] == "invoices")
    assert (invoices["status"], invoices["error_code"]) == ("failed", "zoho.too_many_records")
    assert await one(factory, "SELECT count(*) FROM finance.invoices") == 0  # nothing partial
    assert counts(body)["expenses"] == 4  # the other datasets still landed
    assert body["as_of"] is None  # not every dataset has data yet


async def test_a_failed_dataset_keeps_its_last_good_data(
    connected: ConnectionScope,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
    db_client: AsyncClient,
) -> None:
    await sync_now(runner, connected)
    await login(db_client, OWNER)
    first = await status(db_client, connected)

    zoho.routes["expenses"].mock(return_value=httpx.Response(500, text="oops"))
    runner.clock = lambda: NOW + timedelta(hours=1)
    await sync_now(runner, connected)

    body = await status(db_client, connected)
    expenses = next(d for d in body["datasets"] if d["key"] == "expenses")
    before = next(d for d in first["datasets"] if d["key"] == "expenses")
    assert (body["run"]["status"], expenses["status"], expenses["error_code"]) == (
        "partial",
        "failed",
        "zoho.error",
    )
    assert expenses["last_success_at"] == before["last_success_at"]
    assert expenses["row_count"] == 4
    assert await one(factory, "SELECT count(*) FROM finance.expenses") == 4
    assert body["as_of"] == before["last_success_at"]  # the oldest successful refresh


async def test_rejected_refresh_token_stops_the_run(
    connected: ConnectionScope,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
) -> None:
    zoho.post("https://accounts.zoho.in/oauth/v2/token").mock(
        return_value=httpx.Response(200, json={"error": "invalid_code"})
    )
    # Expire the stored access token so the first request must refresh.
    async with factory.database.sessions() as session:
        secret = await vault.load(session, runner.settings, connected)
        secret["access_expires_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        await vault.store(session, runner.settings, connected, secret)
        await session.commit()

    await sync_now(runner, connected)
    run = (await factory.sql("SELECT status, error_code FROM core.sync_runs") or [])[0]
    assert tuple(run) == ("failed", "connection.needs_reauth")
    assert await one(factory, "SELECT status FROM core.integration_connections") == "needs_reauth"
    written = await one(
        factory, "SELECT count(*) FROM core.connection_datasets WHERE status = 'ok'"
    )
    assert written == 0
    assert zoho.routes["invoices"].call_count == 0  # stopped at the first dataset


# ---------------------------------------------------------------- trigger rules


async def test_trigger_rules(
    connected: ConnectionScope,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
    make_client: Callable[[], AsyncClient],
) -> None:
    await factory.user("viewer@alpha.test")
    await factory.role("alpha-traders", "viewer@alpha.test", Role.VIEWER)
    viewer = make_client()
    csrf = await login(viewer, "viewer@alpha.test")
    url = f"/api/v1/workspaces/{connected.workspace_id}/connections/{connected.connection_id}/sync"
    headers = {"X-CSRF-Token": csrf}

    first = await viewer.post(url, headers=headers)  # viewers may refresh what they can see
    assert first.status_code == 202
    await runner.wait_idle()

    again = await viewer.post(url, headers=headers)
    assert again.status_code == 429
    assert again.json()["code"] == "sync.cooldown"
    assert again.json()["retry_after_seconds"] > 0

    fresh = await viewer.post(url, headers=headers, json={"mode": "if_stale"})
    assert fresh.status_code == 202
    assert await one(factory, "SELECT count(*) FROM core.sync_runs") == 1  # fresh: no new run

    runner.clock = lambda: NOW + timedelta(minutes=20)  # past FINANCE_STALE_AFTER_MINUTES
    stale = await viewer.post(url, headers=headers, json={"mode": "if_stale"})
    assert stale.status_code == 202
    await runner.wait_idle()
    assert await one(factory, "SELECT count(*) FROM core.sync_runs") == 2

    await factory.sql(
        "UPDATE core.integration_connections SET settings = settings || "
        "jsonb_build_object('rate_limit', jsonb_build_object("
        "'limit', 1000, 'remaining', 50, 'reset_at', CAST(:reset AS text)))",
        reset=(NOW + timedelta(hours=5)).isoformat(),
    )
    runner.clock = lambda: NOW + timedelta(minutes=40)
    budget = await viewer.post(url, headers=headers)
    assert budget.status_code == 429
    assert budget.json()["code"] == "sync.budget_low"

    await factory.sql("UPDATE core.integration_connections SET status = 'needs_reauth'")
    blocked = await viewer.post(url, headers=headers)
    assert (blocked.status_code, blocked.json()["code"]) == (409, "connection.needs_reauth")


async def test_one_run_per_connection(
    connected: ConnectionScope, runner: SyncRunner, zoho: respx.MockRouter, factory: Factory
) -> None:
    await factory.sql(
        "INSERT INTO core.sync_runs (id, workspace_id, connection_id, trigger, status, started_at) "
        "VALUES (gen_random_uuid(), :w, :c, 'manual', 'running', :t)",
        w=connected.workspace_id,
        c=connected.connection_id,
        t=NOW - timedelta(minutes=1),
    )
    joined = await runner.trigger(connected, SyncTrigger.MANUAL)
    assert joined.started is False  # a trigger joins the run in progress
    assert await one(factory, "SELECT count(*) FROM core.sync_runs") == 1

    await factory.sql("DELETE FROM core.sync_runs")
    async with factory.database.engine.connect() as other_worker:
        await other_worker.execute(
            select(text(f"pg_advisory_lock({_lock_key(connected.connection_id)})"))
        )
        await sync_now(runner, connected)
        await other_worker.execute(
            select(text(f"pg_advisory_unlock({_lock_key(connected.connection_id)})"))
        )
    assert tuple((await factory.sql("SELECT status, error_code FROM core.sync_runs") or [])[0]) == (
        "failed",
        "sync.busy",
    )
    assert zoho.calls.call_count == 0


async def test_abandoned_runs_are_reaped(
    connected: ConnectionScope, runner: SyncRunner, zoho: respx.MockRouter, factory: Factory
) -> None:
    await factory.sql(
        "INSERT INTO core.sync_runs (id, workspace_id, connection_id, trigger, status, started_at) "
        "VALUES (gen_random_uuid(), :w, :c, 'manual', 'running', :t)",
        w=connected.workspace_id,
        c=connected.connection_id,
        t=NOW - timedelta(minutes=20),
    )
    await sync_now(runner, connected)
    rows = await factory.sql("SELECT status, error_code FROM core.sync_runs ORDER BY started_at")
    assert [tuple(r) for r in rows or []] == [("failed", "sync.abandoned"), ("succeeded", None)]


# ---------------------------------------------------------------- lifecycle and tenancy


async def test_disconnect_purges_the_mirror(
    connected: ConnectionScope,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    factory: Factory,
    db_client: AsyncClient,
) -> None:
    await sync_now(runner, connected)
    zoho.post("https://accounts.zoho.in/oauth/v2/token/revoke").mock(
        return_value=httpx.Response(200, json={})
    )
    csrf = await login(db_client, OWNER)
    response = await db_client.delete(
        f"/api/v1/workspaces/{connected.workspace_id}/connections/{connected.connection_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 204
    for table in (
        "finance.accounts",
        "finance.parties",
        "finance.invoices",
        "finance.payments_received",
        "finance.expenses",
        "finance.payments_made",
        "finance.ledger_monthly_amounts",
        "finance.balance_snapshots",
        "core.connection_datasets",
    ):
        assert await one(factory, f"SELECT count(*) FROM {table}") == 0, table  # noqa: S608


async def test_initial_import_starts_after_choosing_the_organisation(
    factory: Factory,
    db_app: FastAPI,
    runner: SyncRunner,
    zoho: respx.MockRouter,
    db_client: AsyncClient,
) -> None:
    await factory.user(OWNER)
    workspace = await factory.workspace("Alpha Traders", OWNER)
    scope = await zoho_connection(factory, db_app.state.settings, workspace, OWNER)
    await factory.sql(
        "UPDATE core.integration_connections SET status = 'pending', "
        "external_account_id = NULL, external_account_name = NULL"
    )
    zoho.get(f"{API}/organizations").mock(
        return_value=httpx.Response(
            200, json={"code": 0, "organizations": [fixture("organization")["organization"]]}
        )
    )
    zoho.get(f"{API}/organizations/{ZOHO_ORG_ID}").mock(
        return_value=httpx.Response(200, json=fixture("organization"))
    )
    csrf = await login(db_client, OWNER)
    chosen = await db_client.post(
        f"/api/v1/workspaces/{workspace}/connections/{scope.connection_id}/account",
        headers={"X-CSRF-Token": csrf},
        json={"account_id": ZOHO_ORG_ID},
    )
    assert chosen.status_code == 200, chosen.text
    await runner.wait_idle()
    body = await status(db_client, scope)
    assert (body["run"]["trigger"], body["run"]["status"]) == ("initial", "succeeded")
    assert counts(body) == EXPECTED_ROWS


async def test_mirror_rows_cannot_point_at_another_workspaces_connection(
    connected: ConnectionScope, factory: Factory
) -> None:
    await factory.user("owner@beta.test")
    beta = await factory.workspace("Beta Foods", "owner@beta.test")
    with pytest.raises(IntegrityError):
        await factory.sql(
            "INSERT INTO finance.parties (id, workspace_id, connection_id, source_system, "
            "source_record_id, synced_at, sync_run_id, party_type, display_name) VALUES "
            "(gen_random_uuid(), :w, :c, 'zoho-books', 'x', now(), gen_random_uuid(), "
            "'customer', 'Leak')",
            w=beta,
            c=connected.connection_id,
        )


def test_test_dataset_matches_a_real_sync_of_the_test_organisation() -> None:
    """The canonical TEST dataset has the counts a real sync of the trial organisation produces."""
    from clario.domains.finance.testing.fixture_source import test_dataset

    data = test_dataset()
    assert {
        "accounts": len(data.accounts),
        "parties": len(data.parties),
        "invoices": len(data.invoices),
        "payments_received": len(data.payments_received),
        "expenses": len(data.expenses),
        "payments_made": len(data.payments_made),
        "ledger": len(data.ledger),
        "balances": len(data.balances),
    } == {
        "accounts": 67,
        "parties": 4,
        "invoices": 7,
        "payments_received": 3,
        "expenses": 4,
        "payments_made": 1,
        "ledger": 9,
        "balances": 5,
    }
    assert date(2026, 9, 1) in {row.period_month for row in data.ledger}


async def test_operator_commands_act_as_the_workspace_owner(
    connected: ConnectionScope, factory: Factory
) -> None:
    from clario.api.registry import build_registry
    from clario.platform.connections.service import operator_scope

    async with factory.database.sessions() as session:
        scope = await operator_scope(session, build_registry(), "alpha-traders", "zoho-books")
    assert (scope.connection_id, scope.user_id, scope.domain) == (
        connected.connection_id,
        connected.user_id,
        "finance",
    )
