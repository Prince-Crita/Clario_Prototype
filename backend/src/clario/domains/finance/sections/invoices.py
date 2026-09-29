"""The invoice register (plan §22.2): every invoice, newest first, with a cursor (max 200)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from clario.core.errors import ValidationFailedError
from clario.core.pagination import clamp_limit, decode_cursor, encode_cursor
from clario.domains.finance import repository as repo
from clario.domains.finance.sections.common import invoice_out
from clario.domains.finance.sections.context import FinanceContext
from clario.domains.finance.sections.dto import InvoicePage

StatusFilter = Literal["overdue", "unpaid", "paid", "partially_paid", "open", "draft", "void"]


def _after(cursor: str | None) -> tuple[date, str, uuid.UUID] | None:
    if cursor is None:
        return None
    position = decode_cursor(cursor)
    try:
        return (
            date.fromisoformat(str(position["d"])),
            str(position["n"]),
            uuid.UUID(str(position["i"])),
        )
    except (KeyError, ValueError):
        raise ValidationFailedError(
            "cursor is not valid", code="pagination.invalid_cursor"
        ) from None


async def page(
    ctx: FinanceContext,
    *,
    status: StatusFilter | None = None,
    party: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> InvoicePage:
    size = clamp_limit(limit)
    rows = await repo.invoice_page(
        ctx.session,
        ctx.scope,
        today=ctx.today,
        status=status,
        party=party.strip() if party and party.strip() else None,
        after=_after(cursor),
        limit=size + 1,
    )
    more = len(rows) > size
    rows = rows[:size]
    last = rows[-1] if more and rows else None
    return InvoicePage(
        items=[invoice_out(r, ctx.today) for r in rows],
        next_cursor=encode_cursor(
            {"d": last.invoice_date.isoformat(), "n": last.invoice_number, "i": str(last.id)}
        )
        if last
        else None,
    )
