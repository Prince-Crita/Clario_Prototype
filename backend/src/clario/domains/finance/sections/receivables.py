"""Receivables tab (plan §22.2): outstanding, overdue total and count, ageing by days overdue,
receivables by client and the open invoices, most overdue first. Balances as of today."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from clario.domains.finance import models as m
from clario.domains.finance import repository as repo
from clario.domains.finance.ingest import owned
from clario.domains.finance.metrics.receivables import ageing, is_overdue
from clario.domains.finance.sections.common import client_out, invoice_out
from clario.domains.finance.sections.context import FinanceContext
from clario.domains.finance.sections.dto import AgeBucketOut, Receivables

ZERO = Decimal(0)


async def build(ctx: FinanceContext) -> Receivables:
    today = ctx.today
    receivable = await repo.receivable_invoices(ctx.session, ctx.scope)
    overdue = [i for i in receivable if is_overdue(i.status, i.balance, i.due_date, today)]
    rows = await ctx.session.scalars(
        select(m.Invoice).where(
            *owned(m.Invoice, ctx.scope),
            m.Invoice.status.not_in(["draft", "void"]),
            m.Invoice.balance_base > 0,
        )
    )
    invoices = sorted(
        (invoice_out(r, today) for r in rows),
        key=lambda i: (-i.days_overdue, i.due_date or today, i.invoice_number),
    )
    clients = [
        client_out(r)
        for r in await repo.billed_by_party(ctx.session, ctx.scope, today)
        if r.outstanding > 0
    ]
    clients.sort(key=lambda c: (-c.outstanding, c.party_name))
    return Receivables(
        meta=ctx.meta,
        outstanding=sum((i.balance for i in receivable), ZERO),
        overdue=sum((i.balance for i in overdue), ZERO),
        overdue_count=len(overdue),
        open_count=len(receivable),
        ageing=[
            AgeBucketOut(key=b.key, label=b.label, amount=b.amount, count=b.count)
            for b in ageing(receivable, today)
        ],
        by_client=clients,
        invoices=invoices,
    )
