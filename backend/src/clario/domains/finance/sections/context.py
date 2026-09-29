"""What every section needs: the connected organisation, its "today" and fiscal year, freshness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import today_in, utc_now
from clario.core.errors import NotFoundError
from clario.domains.finance.periods import fy_label
from clario.domains.finance.sections.dto import Freshness, Meta, Window
from clario.platform.access.scopes import ConnectionScope
from clario.platform.connections import repository as connection_repo
from clario.platform.connections.service import connection_profile
from clario.platform.sync import repository as sync_repo
from clario.platform.sync.models import RunStatus


@dataclass(frozen=True, slots=True)
class FinanceContext:
    session: AsyncSession
    scope: ConnectionScope
    today: date
    fiscal_year_start_month: int
    meta: Meta


async def load_context(
    session: AsyncSession, scope: ConnectionScope, clock: Callable[[], datetime] = utc_now
) -> FinanceContext:
    connection = await connection_repo.get_live(session, scope, scope.connection_id)
    if connection is None:
        raise NotFoundError("Connection not found.", code="connection.not_found")
    tz, fy_month = connection_profile(connection, scope)
    today = today_in(tz, clock())

    rows = list((await sync_repo.datasets(session, scope)).values())
    written = [r for r in rows if r.last_success_at is not None]
    # "Data as of" = the oldest successful refresh, once every dataset has data (plan §31).
    as_of = min(r.last_success_at for r in written) if rows and len(written) == len(rows) else None  # type: ignore[type-var]
    latest = max(written, key=lambda r: r.last_success_at, default=None)  # type: ignore[arg-type,return-value]
    running = await sync_repo.running_run(session, scope)
    meta = Meta(
        organisation=connection.external_account_name or "Your organisation",
        currency=(connection.settings or {}).get("currency") or scope.base_currency,
        fiscal_year=fy_label(today, fy_month),
        fiscal_year_start_month=fy_month,
        today=today,
        freshness=Freshness(
            as_of=as_of,
            data_version=latest.last_run_id if latest else None,
            sync_state="running" if running and running.status == RunStatus.RUNNING else "idle",
        ),
    )
    return FinanceContext(session, scope, today, fy_month, meta)


def window(start: date, end: date, label: str | None = None) -> Window:
    if label is None:
        label = f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"
    return Window(start=start, end=end, label=label)
