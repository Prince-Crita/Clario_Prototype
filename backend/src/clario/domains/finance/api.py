"""Finance dashboard API (plan §11.2, §25): one endpoint per Command Centre tab, plus the invoice
register. Mounted by the composition root from the Finance DomainModule.

Every response carries `meta.freshness` (data as of, data version, sync state). Opening a tab
starts a background refresh when the data is stale (the on-demand mirror, §31); the response is
served from the mirror immediately.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from clario.core.errors import NotFoundError
from clario.domains.finance.sections import invoices, ledger, overview, receivables, trends
from clario.domains.finance.sections.context import FinanceContext, load_context
from clario.domains.finance.sections.dto import (
    BalanceSheet,
    GstOut,
    InvoicePage,
    Overview,
    Receivables,
    Trends,
)
from clario.platform.access.permissions import Permission
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections.deps import connection_access
from clario.platform.sync.models import SyncTrigger
from clario.platform.sync.service import SyncRunner
from clario.platform.web import SessionDep

router = APIRouter(
    prefix="/workspaces/{workspace_id}/connections/{connection_id}/finance", tags=["finance"]
)
_can_view = Depends(connection_access(Permission.FINANCE_VIEW))


async def finance_scope(scope: ConnectionScope = _can_view) -> ConnectionScope:
    if scope.domain != "finance":  # e.g. an inventory connection's id on a finance path
        raise NotFoundError("Connection not found.", code="connection.not_found")
    return scope


FinanceScope = Annotated[ConnectionScope, Depends(finance_scope)]


async def finance_context(
    scope: FinanceScope, session: SessionDep, request: Request, background: BackgroundTasks
) -> FinanceContext:
    runner: SyncRunner = request.app.state.sync
    # Opening a page refreshes stale data in the background. Not when serverless (`sync_inline`):
    # work after the response is not guaranteed to run there, and running it inside the request
    # would slow every dashboard load. Refresh there is the Sync button (or `clario sync`).
    if not runner.settings.sync_inline:
        background.add_task(runner.start_quietly, scope, SyncTrigger.STALE, None)
    return await load_context(session, scope, runner.clock)


Context = Annotated[FinanceContext, Depends(finance_context)]


@router.get("/overview", response_model=Overview, summary="Overview tab")
async def get_overview(ctx: Context) -> Overview:
    return await overview.build(ctx)


@router.get("/trends", response_model=Trends, summary="Trends & Analysis tab")
async def get_trends(ctx: Context) -> Trends:
    return await trends.build(ctx)


@router.get("/receivables", response_model=Receivables, summary="Receivables tab")
async def get_receivables(ctx: Context) -> Receivables:
    return await receivables.build(ctx)


@router.get("/gst", response_model=GstOut, summary="GST tab (pending the director's definition)")
async def get_gst(ctx: Context) -> GstOut:
    return await ledger.build_gst(ctx)


@router.get(
    "/balance-sheet",
    response_model=BalanceSheet,
    summary="Balance Sheet tab (pending the director's definition)",
)
async def get_balance_sheet(ctx: Context) -> BalanceSheet:
    return await ledger.build_balance_sheet(ctx)


@router.get("/invoices", response_model=InvoicePage, summary="Invoice register, newest first")
async def get_invoices(
    ctx: Context,
    status: Annotated[invoices.StatusFilter | None, Query()] = None,
    party: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> InvoicePage:
    return await invoices.page(ctx, status=status, party=party, cursor=cursor, limit=limit)
