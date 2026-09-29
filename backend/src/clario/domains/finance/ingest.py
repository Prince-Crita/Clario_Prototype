"""Writing canonical records into the mirror (plan §23.3).

`replace_window` = upsert every fetched row by `(connection_id, source_record_id)`, then delete the
connection's rows inside the window that the source no longer returned. Row ids stay stable (so
references between tables survive a re-sync) and deletions or voids at the source are reflected.
It runs inside the dataset's transaction: the whole dataset lands, or none of it does.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from itertools import batched
from typing import Any

from sqlalchemy import ColumnElement, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import utc_now
from clario.core.ids import uuid7
from clario.domains.finance.models import Account, Lineage, Party
from clario.platform.access.scopes import ConnectionScope

BATCH = 500  # rows per INSERT (asyncpg allows 32,767 parameters per statement)
KEYS = frozenset({"id", "workspace_id", "connection_id", "source_record_id"})


def owned(model: type[Lineage], scope: ConnectionScope) -> list[ColumnElement[bool]]:
    return [model.connection_id == scope.connection_id, model.workspace_id == scope.workspace_id]


async def replace_window(
    session: AsyncSession,
    model: type[Lineage],
    scope: ConnectionScope,
    run_id: uuid.UUID,
    rows: Sequence[Mapping[str, Any]],
    *,
    window: ColumnElement[bool] | None = None,
) -> int:
    """Upsert `rows` (each with `source_record_id`) and drop stale rows in `window`. Returns
    the number of rows now mirrored for the window."""
    now = utc_now()
    lineage = {
        "workspace_id": scope.workspace_id,
        "connection_id": scope.connection_id,
        "source_system": scope.integration_key,
        "synced_at": now,
        "sync_run_id": run_id,
    }
    seen: list[str] = []
    for chunk in batched(rows, BATCH):
        values = [{"id": uuid7(), **row, **lineage} for row in chunk]
        seen.extend(str(v["source_record_id"]) for v in values)
        statement = insert(model).values(values)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[model.connection_id, model.source_record_id],
                set_={k: statement.excluded[k] for k in values[0] if k not in KEYS},
            )
        )
    stale = delete(model).where(*owned(model, scope), model.source_record_id.not_in(seen))
    if window is not None:
        stale = stale.where(window)
    await session.execute(stale)
    return len(seen)


async def purge(session: AsyncSession, model: type[Lineage], scope: ConnectionScope) -> None:
    await session.execute(delete(model).where(*owned(model, scope)))


async def party_ids(session: AsyncSession, scope: ConnectionScope) -> dict[str, uuid.UUID]:
    rows = await session.execute(
        select(Party.source_record_id, Party.id).where(*owned(Party, scope))
    )
    return {row[0]: row[1] for row in rows}


async def account_ids(session: AsyncSession, scope: ConnectionScope) -> dict[str, uuid.UUID]:
    rows = await session.execute(
        select(Account.source_record_id, Account.id).where(*owned(Account, scope))
    )
    return {row[0]: row[1] for row in rows}


async def account_ids_by_name(
    session: AsyncSession, scope: ConnectionScope
) -> dict[str, uuid.UUID | None]:
    """Name → id. Names are unique per organisation in Zoho; a duplicate maps to None (unknown)
    rather than to a guess."""
    found: dict[str, uuid.UUID | None] = {}
    rows = await session.execute(select(Account.name, Account.id).where(*owned(Account, scope)))
    for name, id_ in rows:
        key = name.casefold()
        found[key] = None if key in found else id_
    return found


def unique_by_source(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Keep the last row per source id (a source repeating a record must not fail the upsert)."""
    return list({str(r["source_record_id"]): r for r in rows}.values())
