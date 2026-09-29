"""Converters shared by the sections (metric objects → response models)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from clario.core.dates import DateRange, iter_month_starts
from clario.domains.finance import models as m
from clario.domains.finance import repository as repo
from clario.domains.finance.metrics import cash
from clario.domains.finance.metrics.actions import ActionItem
from clario.domains.finance.metrics.receivables import days_overdue, display_status
from clario.domains.finance.sections.context import FinanceContext
from clario.domains.finance.sections.dto import (
    ActionItemOut,
    ClientBilled,
    InvoiceOut,
    MonthFigures,
)


def month_out(row: cash.MonthRow) -> MonthFigures:
    return MonthFigures(
        month=row.month,
        billed=row.billed,
        collected=row.collected,
        expenses=row.expenses,
        net_cash=row.net_cash,
    )


async def month_rows(ctx: FinanceContext, window: DateRange) -> list[cash.MonthRow]:
    """Billed, collected and cash expenses per month of `window` (from the first active month)."""
    billed = await repo.billed_by_month(ctx.session, ctx.scope, window)
    collected = repo.by_month(await repo.collected_by_day(ctx.session, ctx.scope, window))
    spent = repo.by_month(await repo.expenses_by_day(ctx.session, ctx.scope, window))
    return cash.month_rows(iter_month_starts(window.start, window.end), billed, collected, spent)


def action_out(item: ActionItem) -> ActionItemOut:
    return ActionItemOut(
        kind=item.kind.value,
        severity=item.severity.value,
        title=item.title,
        detail=item.detail,
        amount=item.amount,
        reference=item.reference,
        days_overdue=item.days_overdue,
        due_date=item.due_date,
    )


def client_out(row: repo.PartyBilled) -> ClientBilled:
    return ClientBilled(
        party_name=row.party_name,
        billed=row.billed,
        outstanding=row.outstanding,
        overdue=row.overdue,
        has_overdue=row.overdue > 0,
    )


def invoice_out(row: m.Invoice, today: date) -> InvoiceOut:
    return InvoiceOut(
        id=row.id,
        invoice_number=row.invoice_number,
        party_name=row.party_name,
        invoice_date=row.invoice_date,
        due_date=row.due_date,
        total=row.total_base,
        balance=max(row.balance_base, Decimal(0)),
        currency=row.currency,
        total_document=row.total,
        status=display_status(row.status, row.balance_base, row.due_date, today),
        days_overdue=days_overdue(row.due_date, today) if row.balance_base > 0 else 0,
    )
