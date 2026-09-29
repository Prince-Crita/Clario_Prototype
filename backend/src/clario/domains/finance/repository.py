"""Scoped SQL aggregates over the finance mirror (plan §24.1).

Only sums, counts and rows: every formula lives in `metrics/`. Every query is filtered by the
ConnectionScope (connection AND workspace), so a caller can never read another tenant's rows.
Aggregates use base-currency amounts.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from clario.core.dates import DateRange, month_start
from clario.domains.finance import models as m
from clario.domains.finance.ingest import owned
from clario.domains.finance.metrics.receivables import NOT_RECEIVABLE, OpenInvoice
from clario.domains.finance.schemas import PnlSection
from clario.platform.access.scopes import ConnectionScope

ZERO = Decimal(0)


def _month(column: Any) -> Any:
    return cast(func.date_trunc("month", column), Date)


def _billable() -> Any:
    return m.Invoice.status.not_in(NOT_RECEIVABLE)


# ---------------------------------------------------------------- ledger (accrual)


async def section_totals(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> dict[PnlSection, Decimal]:
    rows = await session.execute(
        select(m.LedgerMonthlyAmount.section, func.sum(m.LedgerMonthlyAmount.amount))
        .where(
            *owned(m.LedgerMonthlyAmount, scope),
            m.LedgerMonthlyAmount.period_month.between(month_start(window.start), window.end),
        )
        .group_by(m.LedgerMonthlyAmount.section)
    )
    return {PnlSection(section): total for section, total in rows.all()}


async def ledger_by_account(
    session: AsyncSession,
    scope: ConnectionScope,
    window: DateRange,
    sections: Sequence[PnlSection],
) -> list[tuple[str, Decimal]]:
    """Per account, largest first (e.g. the expense mix)."""
    total = func.sum(m.LedgerMonthlyAmount.amount)
    rows = await session.execute(
        select(m.LedgerMonthlyAmount.account_name, total)
        .where(
            *owned(m.LedgerMonthlyAmount, scope),
            m.LedgerMonthlyAmount.period_month.between(month_start(window.start), window.end),
            m.LedgerMonthlyAmount.section.in_([s.value for s in sections]),
        )
        .group_by(m.LedgerMonthlyAmount.account_name)
        .having(total != 0)
        .order_by(total.desc(), m.LedgerMonthlyAmount.account_name)
    )
    return [(name, amount) for name, amount in rows.all()]


# ---------------------------------------------------------------- documents (billed / cash)


async def billed_by_month(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> dict[date, Decimal]:
    month = _month(m.Invoice.invoice_date)
    rows = await session.execute(
        select(month, func.sum(m.Invoice.total_base))
        .where(
            *owned(m.Invoice, scope),
            _billable(),
            m.Invoice.invoice_date.between(window.start, window.end),
        )
        .group_by(month)
    )
    return {row[0]: row[1] for row in rows.all()}


async def collected_by_day(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> dict[date, Decimal]:
    rows = await session.execute(
        select(m.PaymentReceived.payment_date, func.sum(m.PaymentReceived.amount_base))
        .where(
            *owned(m.PaymentReceived, scope),
            m.PaymentReceived.payment_date.between(window.start, window.end),
        )
        .group_by(m.PaymentReceived.payment_date)
    )
    return {row[0]: row[1] for row in rows.all()}


async def expenses_by_day(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> dict[date, Decimal]:
    rows = await session.execute(
        select(m.Expense.expense_date, func.sum(m.Expense.total_base))
        .where(*owned(m.Expense, scope), m.Expense.expense_date.between(window.start, window.end))
        .group_by(m.Expense.expense_date)
    )
    return {row[0]: row[1] for row in rows.all()}


async def expenses_by_category_month(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> list[tuple[date, str, Decimal]]:
    month = _month(m.Expense.expense_date)
    rows = await session.execute(
        select(month, m.Expense.account_name, func.sum(m.Expense.total_base))
        .where(*owned(m.Expense, scope), m.Expense.expense_date.between(window.start, window.end))
        .group_by(month, m.Expense.account_name)
    )
    return [(day, name, total) for day, name, total in rows.all()]


def by_month(daily: dict[date, Decimal]) -> dict[date, Decimal]:
    months: dict[date, Decimal] = {}
    for day, amount in daily.items():
        key = month_start(day)
        months[key] = months.get(key, ZERO) + amount
    return months


# ---------------------------------------------------------------- invoices


def _open_invoice(row: m.Invoice) -> OpenInvoice:
    return OpenInvoice(
        invoice_number=row.invoice_number,
        party_name=row.party_name,
        invoice_date=row.invoice_date,
        due_date=row.due_date,
        total=row.total_base,
        balance=row.balance_base,
        status=row.status,
    )


async def receivable_invoices(session: AsyncSession, scope: ConnectionScope) -> list[OpenInvoice]:
    rows = await session.scalars(
        select(m.Invoice)
        .where(*owned(m.Invoice, scope), _billable(), m.Invoice.balance_base > 0)
        .order_by(m.Invoice.due_date, m.Invoice.invoice_number)
    )
    return [_open_invoice(r) for r in rows]


@dataclass(frozen=True, slots=True)
class PartyBilled:
    party_name: str
    billed: Decimal
    outstanding: Decimal
    overdue: Decimal


async def billed_by_party(
    session: AsyncSession, scope: ConnectionScope, today: date
) -> list[PartyBilled]:
    """Lifetime billed per client (draft/void excluded), with what is outstanding and overdue."""
    overdue = case(
        (and_(m.Invoice.balance_base > 0, m.Invoice.due_date < today), m.Invoice.balance_base),
        else_=0,
    )
    billed = func.sum(m.Invoice.total_base)
    rows = await session.execute(
        select(
            m.Invoice.party_name,
            billed,
            func.sum(func.greatest(m.Invoice.balance_base, 0)),
            func.sum(overdue),
        )
        .where(*owned(m.Invoice, scope), _billable())
        .group_by(m.Invoice.party_name)
        .order_by(billed.desc(), m.Invoice.party_name)
    )
    return [PartyBilled(name, b, o, d) for name, b, o, d in rows.all()]


@dataclass(frozen=True, slots=True)
class RegisterTotals:
    count: int
    billed: Decimal
    balance: Decimal


async def register_totals(session: AsyncSession, scope: ConnectionScope) -> RegisterTotals:
    row = (
        await session.execute(
            select(
                func.count(m.Invoice.id),
                func.coalesce(func.sum(m.Invoice.total_base), 0),
                func.coalesce(func.sum(func.greatest(m.Invoice.balance_base, 0)), 0),
            ).where(*owned(m.Invoice, scope), _billable())
        )
    ).one()
    return RegisterTotals(int(row[0]), Decimal(row[1]), Decimal(row[2]))


async def invoice_page(
    session: AsyncSession,
    scope: ConnectionScope,
    *,
    today: date,
    status: str | None,
    party: str | None,
    after: tuple[date, str, uuid.UUID] | None,
    limit: int,
    number: str | None = None,
    window: DateRange | None = None,
    party_exact: bool = False,
) -> list[m.Invoice]:
    """Newest first; keyset pagination on (invoice_date, invoice_number, id)."""
    statement = select(m.Invoice).where(*owned(m.Invoice, scope))
    if status == "overdue":
        statement = statement.where(
            _billable(), m.Invoice.balance_base > 0, m.Invoice.due_date < today
        )
    elif status == "unpaid":
        statement = statement.where(_billable(), m.Invoice.balance_base > 0)
    elif status is not None:
        statement = statement.where(m.Invoice.status == status)
    if party and party_exact:
        statement = statement.where(m.Invoice.party_name == party)
    elif party:
        pattern = "%" + party.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        statement = statement.where(m.Invoice.party_name.ilike(pattern, escape="\\"))
    if number:
        statement = statement.where(func.upper(m.Invoice.invoice_number) == number.strip().upper())
    if window is not None:
        statement = statement.where(m.Invoice.invoice_date.between(window.start, window.end))
    if after is not None:
        day, number, id_ = after
        statement = statement.where(
            or_(
                m.Invoice.invoice_date < day,
                and_(m.Invoice.invoice_date == day, m.Invoice.invoice_number < number),
                and_(
                    m.Invoice.invoice_date == day,
                    m.Invoice.invoice_number == number,
                    m.Invoice.id < id_,
                ),
            )
        )
    rows = await session.scalars(
        statement.order_by(
            m.Invoice.invoice_date.desc(), m.Invoice.invoice_number.desc(), m.Invoice.id.desc()
        ).limit(limit)
    )
    return list(rows)


# ---------------------------------------------------------------- balances


@dataclass(frozen=True, slots=True)
class BalanceLine:
    account_name: str
    group: str
    balance: Decimal
    category: str | None
    tax_role: str | None


async def latest_balances(
    session: AsyncSession, scope: ConnectionScope
) -> tuple[date | None, list[BalanceLine]]:
    as_of = await session.scalar(
        select(func.max(m.BalanceSnapshot.as_of_date)).where(*owned(m.BalanceSnapshot, scope))
    )
    if as_of is None:
        return None, []
    rows = await session.execute(
        select(
            m.BalanceSnapshot.account_name,
            m.BalanceSnapshot.account_group,
            m.BalanceSnapshot.balance,
            m.Account.category,
            m.Account.tax_role,
        )
        .outerjoin(m.Account, m.Account.id == m.BalanceSnapshot.account_id)
        .where(*owned(m.BalanceSnapshot, scope), m.BalanceSnapshot.as_of_date == as_of)
        .order_by(m.BalanceSnapshot.account_group, m.BalanceSnapshot.account_name)
    )
    return as_of, [BalanceLine(*row) for row in rows.all()]


# ---------------------------------------------------------------- assistant lookups


async def section_totals_by_month(
    session: AsyncSession, scope: ConnectionScope, window: DateRange
) -> dict[date, dict[PnlSection, Decimal]]:
    rows = await session.execute(
        select(
            m.LedgerMonthlyAmount.period_month,
            m.LedgerMonthlyAmount.section,
            func.sum(m.LedgerMonthlyAmount.amount),
        )
        .where(
            *owned(m.LedgerMonthlyAmount, scope),
            m.LedgerMonthlyAmount.period_month.between(month_start(window.start), window.end),
        )
        .group_by(m.LedgerMonthlyAmount.period_month, m.LedgerMonthlyAmount.section)
    )
    months: dict[date, dict[PnlSection, Decimal]] = {}
    for month, section, total in rows.all():
        months.setdefault(month, {})[PnlSection(section)] = total
    return months


async def party_names(session: AsyncSession, scope: ConnectionScope) -> list[str]:
    """Every client name seen on invoices or payments (for resolving "them" / a typed name)."""
    invoices = await session.scalars(
        select(m.Invoice.party_name).where(*owned(m.Invoice, scope)).distinct()
    )
    payments = await session.scalars(
        select(m.PaymentReceived.party_name).where(*owned(m.PaymentReceived, scope)).distinct()
    )
    return sorted({*invoices, *payments} - {""})


@dataclass(frozen=True, slots=True)
class PaymentLine:
    payment_date: date
    amount: Decimal  # base currency
    reference: str | None


async def payments_from(
    session: AsyncSession, scope: ConnectionScope, party_name: str, limit: int
) -> tuple[Decimal, list[PaymentLine]]:
    """Total received from one client (all mirrored payments) and the most recent ones."""
    where = [*owned(m.PaymentReceived, scope), m.PaymentReceived.party_name == party_name]
    total = await session.scalar(
        select(func.coalesce(func.sum(m.PaymentReceived.amount_base), 0)).where(*where)
    )
    rows = await session.execute(
        select(
            m.PaymentReceived.payment_date,
            m.PaymentReceived.amount_base,
            m.PaymentReceived.reference,
        )
        .where(*where)
        .order_by(m.PaymentReceived.payment_date.desc())
        .limit(limit)
    )
    return Decimal(total or 0), [PaymentLine(*r) for r in rows.all()]
